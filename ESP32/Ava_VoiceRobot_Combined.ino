#include <TFT_eSPI.h>
#include <math.h>
#include <string.h>
#include <ctype.h>
#include "driver/i2s.h"

// ==========================================
// DISPLAY CONFIGURATION
// ==========================================

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite face = TFT_eSprite(&tft);

#define BG       0x0861
#define CYAN     0x07FF
#define BLUE     0x04FF
#define WHITE    0xFFFF
#define DARK     0x0010

const int FW = 280;
const int FH = 170;
const int FX = 20;
const int FY = 45;

bool spriteReady = false;

// ==========================================
// MICROPHONE CONFIGURATION
// ==========================================

#define I2S_WS   25
#define I2S_SD   33
#define I2S_SCK  26

#define SAMPLE_RATE 16000
#define RECORD_SECONDS 1

#define TOTAL_SAMPLES (SAMPLE_RATE * RECORD_SECONDS)
#define BUFFER_SIZE 128

int32_t inputSamples[BUFFER_SIZE];
int16_t outputSamples[BUFFER_SIZE];

uint32_t samplesSent = 0;
bool recording = false;

#define BUTTON_PIN 32

bool lastButtonReading = HIGH;
bool stableButtonState = HIGH;
unsigned long lastButtonChange = 0;

// ==========================================
// AVA EXPRESSIONS
// ==========================================

enum FaceState {
  IDLE,
  LISTENING,
  THINKING,
  SPEAKING,
  HAPPY,
  SAD,
  SURPRISED,
  SLEEPING,
  WAKING
};

FaceState currentState = IDLE;

unsigned long lastFrame = 0;
unsigned long nextBlink = 0;
unsigned long blinkStarted = 0;
unsigned long wakingStarted = 0;

bool blinking = false;
int animationFrame = 0;

// ==========================================
// SERIAL COMMAND HANDLING
// ==========================================

char commandBuffer[32];
int commandIndex = 0;

void changeState(FaceState newState) {

  if (currentState == newState) return;

  currentState = newState;

  if (newState == WAKING) {
    wakingStarted = millis();
  }

  blinking = false;
  nextBlink = millis() + random(2500, 5000);
}

void processCommand(char *command) {

  for (int i = 0; command[i]; i++) {
    command[i] = toupper(command[i]);
  }

  if (strcmp(command, "IDLE") == 0) {
    changeState(IDLE);
  }
  else if (strcmp(command, "LISTENING") == 0) {
    changeState(LISTENING);
  }
  else if (strcmp(command, "THINKING") == 0) {
    changeState(THINKING);
  }
  else if (strcmp(command, "SPEAKING") == 0) {
    changeState(SPEAKING);
  }
  else if (strcmp(command, "HAPPY") == 0) {
    changeState(HAPPY);
  }
  else if (strcmp(command, "SAD") == 0) {
    changeState(SAD);
  }
  else if (strcmp(command, "SURPRISED") == 0) {
    changeState(SURPRISED);
  }
  else if (strcmp(command, "SLEEP") == 0) {
    changeState(SLEEPING);
  }
  else if (strcmp(command, "WAKING") == 0) {
    changeState(WAKING);
  }
  else if (
    strcmp(command, "RECORD") == 0 ||
    strcmp(command, "RECORD_SLEEP") == 0
  ) {
    samplesSent = 0;
    recording = true;

    if (strcmp(command, "RECORD") == 0) {
      changeState(LISTENING);
    }
  }
}

void receiveCommands() {

  if (recording) return;

  while (Serial.available() > 0) {

    char c = Serial.read();

    if (c == '\n') {

      commandBuffer[commandIndex] = '\0';

      if (commandIndex > 0) {
        processCommand(commandBuffer);
      }

      commandIndex = 0;
    }
    else if (c != '\r') {

      if (commandIndex < sizeof(commandBuffer) - 1) {
        commandBuffer[commandIndex++] = c;
      }
      else {
        commandIndex = 0;
      }
    }
  }
}

// ==========================================
// PHYSICAL WAKE BUTTON
// ==========================================

void checkWakeButton() {

  if (recording || currentState != SLEEPING) return;

  bool reading = digitalRead(BUTTON_PIN);

  if (reading != lastButtonReading) {
    lastButtonChange = millis();
    lastButtonReading = reading;
  }

  if (millis() - lastButtonChange >= 40) {

    if (reading != stableButtonState) {

      stableButtonState = reading;

      if (stableButtonState == LOW) {
        changeState(WAKING);
        Serial.println("WAKE");
      }
    }
  }
}

// ==========================================
// EYE DRAWING
// ==========================================

void drawEye(int x, int openness, int lookX, int lookY) {

  int eyeW = 52;
  int eyeH = max(3, openness);

  int top = 79 - eyeH / 2;

  face.fillRoundRect(
    x - eyeW / 2 - 2,
    top - 2,
    eyeW + 4,
    eyeH + 4,
    15,
    BLUE
  );

  face.fillRoundRect(
    x - eyeW / 2,
    top,
    eyeW,
    eyeH,
    13,
    WHITE
  );

  if (eyeH > 13) {

    int irisY = 79 + lookY;

    irisY = constrain(
      irisY,
      top + 9,
      top + eyeH - 9
    );

    int irisX = x + lookX;

    face.fillCircle(irisX, irisY, 13, CYAN);
    face.fillCircle(irisX, irisY, 7, DARK);

    face.fillCircle(irisX - 4, irisY - 5, 3, WHITE);
    face.fillCircle(irisX + 4, irisY + 4, 2, WHITE);
  }
}

// ==========================================
// EYEBROWS
// ==========================================

void drawEyebrow(int x, int y, int curve, int angle) {

  int leftX = x - 25;
  int rightX = x + 25;

  int leftY = y + angle;
  int rightY = y - angle;

  face.drawLine(leftX, leftY, x, y - curve, CYAN);
  face.drawLine(x, y - curve, rightX, rightY, CYAN);

  face.drawLine(
    leftX, leftY - 1,
    x, y - curve - 1,
    WHITE
  );
}

// ==========================================
// MOUTH
// ==========================================

void drawMouth(int type) {

  int cx = 140;
  int cy = 140;

  switch (type) {

    case 0:
      face.drawLine(124, cy, 156, cy, CYAN);
      break;

    case 1:
      face.drawLine(115, cy - 2, 125, cy + 7, CYAN);
      face.drawLine(125, cy + 7, 140, cy + 11, CYAN);
      face.drawLine(140, cy + 11, 155, cy + 7, CYAN);
      face.drawLine(155, cy + 7, 165, cy - 2, CYAN);
      break;

    case 2:
      face.fillEllipse(cx, cy + 2, 11, 15, CYAN);
      face.fillEllipse(cx, cy + 2, 7, 10, DARK);
      break;

    case 3: {
      int mouthH = 4 + (animationFrame % 4) * 3;

      face.fillEllipse(cx, cy, 16, mouthH, CYAN);
      face.fillEllipse(cx, cy, 11, max(1, mouthH - 2), DARK);
      break;
    }

    case 4:
      face.drawLine(121, cy + 9, 130, cy + 1, CYAN);
      face.drawLine(130, cy + 1, 150, cy + 1, CYAN);
      face.drawLine(150, cy + 1, 159, cy + 9, CYAN);
      break;

    case 5:
      face.drawLine(127, cy + 2, 153, cy + 2, CYAN);
      break;
  }
}

// ==========================================
// FACE RENDERING
// ==========================================

void renderFace(
  int leftEye,
  int rightEye,
  int leftLook,
  int rightLook,
  int lookY,
  int browY,
  int browCurve,
  int browAngle,
  int mouthType
) {

  face.fillSprite(BG);

  face.drawRoundRect(8, 8, 264, 154, 20, BLUE);

  face.drawFastHLine(20, 18, 35, CYAN);
  face.drawFastHLine(225, 18, 35, CYAN);

  drawEyebrow(78, browY, browCurve, browAngle);
  drawEyebrow(202, browY, browCurve, -browAngle);

  drawEye(78, leftEye, leftLook, lookY);
  drawEye(202, rightEye, rightLook, lookY);

  drawMouth(mouthType);

  face.pushSprite(FX, FY);
}

// ==========================================
// FACE ANIMATION
// ==========================================

void animateFace() {

  unsigned long now = millis();

  if (now - lastFrame < 50) return;

  lastFrame = now;
  animationFrame++;

  int leftEye = 42;
  int rightEye = 42;

  int leftLook = 0;
  int rightLook = 0;
  int lookY = 0;

  int browY = 48;
  int browCurve = 9;
  int browAngle = 0;

  int mouthType = 0;

  switch (currentState) {

    case IDLE:
      leftLook = sin(now / 1100.0) * 4;
      rightLook = leftLook;
      break;

    case LISTENING:
      leftEye = 46;
      rightEye = 46;

      leftLook = sin(now / 400.0) * 3;
      rightLook = leftLook;

      browY = 44;
      browCurve = 12;
      break;

    case THINKING:
      leftLook = -5;
      rightLook = -5;
      lookY = -5;

      browY = 43;
      browCurve = 8;
      browAngle = 7;
      break;

    case SPEAKING:
      leftEye = 39;
      rightEye = 39;

      leftLook = sin(now / 350.0) * 3;
      rightLook = leftLook;

      mouthType = 3;
      break;

    case HAPPY:
      leftEye = 29 + sin(now / 180.0) * 4;
      rightEye = leftEye;

      browY = 45;
      browCurve = 15;

      mouthType = 1;
      break;

    case SAD:
      leftEye = 31;
      rightEye = 31;

      browY = 53;
      browCurve = 5;
      browAngle = -9;

      mouthType = 4;
      break;

    case SURPRISED:
      leftEye = 54;
      rightEye = 54;

      browY = 29;
      browCurve = 14;

      mouthType = 2;
      break;

    case SLEEPING:
      leftEye = 2;
      rightEye = 2;

      browY = 52;
      browCurve = 5;

      mouthType = 5;
      break;

    case WAKING: {

      float progress = (now - wakingStarted) / 1200.0f;
      progress = constrain(progress, 0.0f, 1.0f);

      int openness = 2 + (int)(40 * progress);

      leftEye = openness;
      rightEye = openness;

      browY = 48 - (int)(4 * progress);
      browCurve = 9 + (int)(3 * progress);

      mouthType = 0;
      break;
    }
  }

  if (currentState == WAKING && now - wakingStarted >= 1200) {
    changeState(IDLE);
  }

  if (
    currentState != SLEEPING &&
    currentState != WAKING &&
    !blinking &&
    now >= nextBlink
  ) {
    blinking = true;
    blinkStarted = now;
  }

  if (
    blinking &&
    currentState != SLEEPING &&
    currentState != WAKING
  ) {

    leftEye = 3;
    rightEye = 3;

    if (now - blinkStarted >= 150) {
      blinking = false;
      nextBlink = now + random(2500, 5000);
    }
  }

  renderFace(
    leftEye,
    rightEye,
    leftLook,
    rightLook,
    lookY,
    browY,
    browCurve,
    browAngle,
    mouthType
  );
}

// ==========================================
// MICROPHONE INITIALIZATION
// ==========================================

void setupMicrophone() {

  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 128,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };

  esp_err_t result = i2s_driver_install(
    I2S_NUM_0,
    &config,
    0,
    NULL
  );

  if (result != ESP_OK) {
    Serial.println("I2S INSTALL ERROR");
    return;
  }

  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

// ==========================================
// CONTROLLED MICROPHONE STREAMING
// ==========================================

void streamMicrophone() {
    if (!recording) return;

    int32_t inputSamples[BUFFER_SIZE];
    int16_t outputSamples[BUFFER_SIZE];

    uint32_t samplesSent = 0;

    while (samplesSent < TOTAL_SAMPLES) {
        size_t bytesRead = 0;

        esp_err_t result = i2s_read(
            I2S_NUM_0,
            inputSamples,
            sizeof(inputSamples),
            &bytesRead,
            pdMS_TO_TICKS(1000)
        );

        if (result != ESP_OK || bytesRead == 0) {
            continue;
        }

        uint32_t sampleCount = bytesRead / sizeof(int32_t);

        if (sampleCount > TOTAL_SAMPLES - samplesSent) {
            sampleCount = TOTAL_SAMPLES - samplesSent;
        }

        for (uint32_t i = 0; i < sampleCount; i++) {
            outputSamples[i] = (int16_t)(inputSamples[i] >> 14);
        }

        size_t bytesToSend = sampleCount * sizeof(int16_t);
        size_t bytesWritten = 0;

        while (bytesWritten < bytesToSend) {
            size_t written = Serial.write(
                (uint8_t*)outputSamples + bytesWritten,
                bytesToSend - bytesWritten
            );

            if (written > 0) {
                bytesWritten += written;
            }
        }

        samplesSent += sampleCount;
    }

    Serial.flush();

    recording = false;

    Serial.printf("\nFRAME_DONE:%lu\n", (unsigned long)samplesSent);
}

// ==========================================
// SETUP
// ==========================================

void setup() {

  Serial.begin(921600);

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  lastButtonReading = digitalRead(BUTTON_PIN);
  stableButtonState = lastButtonReading;

  tft.init();
  tft.setRotation(1);
  tft.fillScreen(BG);

  face.setColorDepth(8);

  if (face.createSprite(FW, FH) == nullptr) {
    spriteReady = false;
    Serial.println("FACE BUFFER ERROR");
    return;
  }

  spriteReady = true;

  randomSeed(micros());

  tft.setTextColor(CYAN, BG);
  tft.setTextSize(2);
  tft.setCursor(140, 12);
  tft.print("AVA");

  setupMicrophone();

  changeState(SLEEPING);
}

// ==========================================
// MAIN LOOP
// ==========================================

void loop() {

  receiveCommands();

  checkWakeButton();

  streamMicrophone();

  if (spriteReady) {
    animateFace();
  }
}