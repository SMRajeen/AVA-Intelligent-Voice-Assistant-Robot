
#include <TFT_eSPI.h>
#include <math.h>

TFT_eSPI tft = TFT_eSPI();
TFT_eSprite face = TFT_eSprite(&tft);

#define BG       0x0861
#define CYAN     0x07FF
#define BLUE     0x04FF
#define WHITE    0xFFFF
#define DARK     0x0010
#define PURPLE   0xB81F
#define PINK     0xF81F
#define YELLOW   0xFFE0

const int FW = 280;
const int FH = 170;
const int FX = 20;
const int FY = 45;

enum Expression {
  NORMAL,
  HAPPY,
  SURPRISED,
  SLEEPY,
  CURIOUS,
  TALKING,
  SAD
};

Expression expression = NORMAL;

unsigned long lastFrame = 0;
unsigned long expressionStarted = 0;
unsigned long nextBlink = 0;
unsigned long blinkStarted = 0;

bool blinking = false;
bool spriteReady = false;

int pupilX = 0;
int pupilY = 0;

// ----------------------------------
// Eye drawing
// ----------------------------------

void drawEye(int x, int openness, int lookX, int lookY) {

  int eyeW = 52;
  int eyeH = openness;

  if (eyeH < 3) eyeH = 3;

  int top = 79 - eyeH / 2;

  // Eye outline
  face.fillRoundRect(
    x - eyeW / 2 - 2,
    top - 2,
    eyeW + 4,
    eyeH + 4,
    15,
    BLUE
  );

  // Eye interior
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

    if (irisY > top + eyeH - 9) irisY = top + eyeH - 9;
    if (irisY < top + 9) irisY = top + 9;

    int irisX = x + lookX;

    // Iris and pupil
    face.fillCircle(irisX, irisY, 13, CYAN);
    face.fillCircle(irisX, irisY, 7, DARK);

    // Eye reflections
    face.fillCircle(irisX - 4, irisY - 5, 3, WHITE);
    face.fillCircle(irisX + 4, irisY + 4, 2, WHITE);
  }
}

// ----------------------------------
// Eyebrows
// ----------------------------------

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

// ----------------------------------
// Mouth
// ----------------------------------

void drawMouth(int type, int animation) {

  int cx = 140;
  int cy = 140;

  switch (type) {

    // Neutral
    case 0:

      face.drawLine(124, cy, 156, cy, CYAN);
      face.drawLine(124, cy, 140, cy + 4, CYAN);
      face.drawLine(140, cy + 4, 156, cy, CYAN);

      break;

    // Happy smile
    case 1:

      face.drawLine(115, cy - 2, 125, cy + 7, CYAN);
      face.drawLine(125, cy + 7, 140, cy + 11, CYAN);
      face.drawLine(140, cy + 11, 155, cy + 7, CYAN);
      face.drawLine(155, cy + 7, 165, cy - 2, CYAN);

      break;

    // Surprised open mouth
    case 2:

      face.fillEllipse(cx, cy + 2, 11, 15, CYAN);
      face.fillEllipse(cx, cy + 2, 7, 10, DARK);

      break;

    // Talking mouth
    case 3: {

      int mouthH = 4 + (animation % 3) * 4;

      face.fillEllipse(cx, cy, 16, mouthH, CYAN);
      face.fillEllipse(cx, cy, 11, mouthH - 2, DARK);

      break;
    }

    // Sad mouth
    case 4:

      face.drawLine(121, cy + 9, 130, cy + 1, CYAN);
      face.drawLine(130, cy + 1, 150, cy + 1, CYAN);
      face.drawLine(150, cy + 1, 159, cy + 9, CYAN);

      break;

    // Sleepy
    case 5:

      face.drawLine(127, cy + 2, 153, cy + 2, CYAN);

      break;
  }
}

// ----------------------------------
// Expression renderer
// ----------------------------------

void renderFace(
  int leftEye,
  int rightEye,
  int leftLook,
  int rightLook,
  int lookY,
  int browY,
  int browCurve,
  int browAngle,
  int mouthType,
  int animation
) {

  face.fillSprite(BG);

  // Decorative subtle eye glow
  face.drawRoundRect(8, 8, 264, 154, 20, BLUE);

  // Eyebrows
  drawEyebrow(78, browY, browCurve, browAngle);
  drawEyebrow(202, browY, browCurve, -browAngle);

  // Eyes
  drawEye(78, leftEye, leftLook, lookY);
  drawEye(202, rightEye, rightLook, lookY);

  // Mouth
  drawMouth(mouthType, animation);

  // Display completed face
  face.pushSprite(FX, FY);
}

// ----------------------------------
// Select expression
// ----------------------------------

void changeExpression(Expression next) {

  expression = next;
  expressionStarted = millis();

  if (expression == NORMAL) {
    nextBlink = millis() + random(2500, 5000);
  }

  blinking = false;
}

// ----------------------------------
// Setup
// ----------------------------------

void setup() {

  Serial.begin(115200);

  tft.init();
  tft.setRotation(1);

  tft.fillScreen(BG);

  face.setColorDepth(8);

  if (face.createSprite(FW, FH) == nullptr) {

    Serial.println("FACE BUFFER ERROR");

    Serial.print("Free heap: ");
    Serial.println(ESP.getFreeHeap());

    return;
  }

  spriteReady = true;

  randomSeed(micros());

  tft.setTextColor(CYAN, BG);
  tft.setTextSize(2);
  tft.setCursor(140, 12);
  tft.print("AVA");

  changeExpression(NORMAL);

  Serial.println("AVA FACE READY");
  Serial.print("Free heap: ");
  Serial.println(ESP.getFreeHeap());
}

// ----------------------------------
// Main animation
// ----------------------------------

void loop() {

  if (!spriteReady) return;

  unsigned long now = millis();

  // 20 FPS
  if (now - lastFrame < 50) return;

  lastFrame = now;

  unsigned long elapsed = now - expressionStarted;

  int leftEye = 42;
  int rightEye = 42;

  int leftLook = 0;
  int rightLook = 0;
  int lookY = 0;

  int browY = 48;
  int browCurve = 9;
  int browAngle = 0;

  int mouthType = 0;

  int animation = elapsed / 100;

  // Automatic expression sequence
  switch (expression) {

    case NORMAL:

      mouthType = 0;

      // Automatic blink
      if (!blinking && now >= nextBlink) {
        blinking = true;
        blinkStarted = now;
      }

      if (blinking) {
        leftEye = 3;
        rightEye = 3;

        if (now - blinkStarted >= 170) {
          blinking = false;
          nextBlink = now + random(2500, 5000);
        }
      }

      // Look around
      leftLook = sin(now / 1100.0) * 5;
      rightLook = leftLook;

      if (elapsed > 6500) {
        changeExpression(HAPPY);
      }

      break;

    case HAPPY:

      leftEye = 29 + sin(now / 180.0) * 4;
      rightEye = leftEye;

      browY = 45;
      browCurve = 15;

      mouthType = 1;

      if (elapsed > 3500) {
        changeExpression(SURPRISED);
      }

      break;

    case SURPRISED:

      leftEye = 54;
      rightEye = 54;

      browY = 29;
      browCurve = 14;

      mouthType = 2;

      if (elapsed > 2500) {
        changeExpression(CURIOUS);
      }

      break;

    case CURIOUS:

      leftLook = 9;
      rightLook = 9;

      browY = 43;
      browAngle = 9;

      mouthType = 0;

      if (elapsed > 3000) {
        changeExpression(SLEEPY);
      }

      break;

    case SLEEPY:

      leftEye = 15;
      rightEye = 15;

      browY = 57;
      browCurve = 4;

      mouthType = 5;

      if (elapsed > 3500) {
        changeExpression(TALKING);
      }

      break;

    case TALKING:

      leftEye = 37;
      rightEye = 37;

      leftLook = sin(now / 350.0) * 3;
      rightLook = leftLook;

      mouthType = 3;

      if (elapsed > 5000) {
        changeExpression(SAD);
      }

      break;

    case SAD:

      leftEye = 31;
      rightEye = 31;

      browY = 53;
      browCurve = 5;
      browAngle = -9;

      mouthType = 4;

      if (elapsed > 3000) {
        changeExpression(NORMAL);
      }

      break;
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
    mouthType,
    animation
  );
}
