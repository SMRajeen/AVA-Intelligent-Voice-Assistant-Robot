
#include "driver/i2s.h"

#define I2S_WS   25
#define I2S_SD   33
#define I2S_SCK  26

#define SAMPLE_RATE 16000
#define BUFFER_SIZE 512

int32_t inputSamples[BUFFER_SIZE];
int16_t outputSamples[BUFFER_SIZE];

void setup() {
  Serial.begin(921600);

  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 256,
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

  i2s_driver_install(I2S_NUM_0, &config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void loop() {
  size_t bytesRead = 0;

  esp_err_t result = i2s_read(
    I2S_NUM_0,
    inputSamples,
    sizeof(inputSamples),
    &bytesRead,
    portMAX_DELAY
  );

  if (result == ESP_OK && bytesRead > 0) {
    int sampleCount = bytesRead / sizeof(int32_t);

    for (int i = 0; i < sampleCount; i++) {
      outputSamples[i] = (int16_t)(inputSamples[i] >> 14);
    }

    Serial.write(
      (uint8_t*)outputSamples,
      sampleCount * sizeof(int16_t)
    );
  }
}
