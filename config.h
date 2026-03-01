#ifndef __CONFIG_H__
#define __CONFIG_H__

// GPRS
#define gprsApn          "gprs.swisscom.ch"
#define gprsUser         ""
#define gprsPass         ""

// Server Settings
#define server_ip        "api.eagleshot.org"
#define server_port      3000
#define resource         "/upload"

#define WIFI_SSID        "WiFi SSID"
#define WIFI_PASSWORD    "WIFI PASSWORD"

#define WIFI_AP_SSID     "T-SIMCAM-"
#define WIFI_AP_PASSWORD "12345678"

// Corresponding version of board screen printing
#define USE_SIM_CAM_V1_2
// #define USE_SIM_CAM_V1_3    //Add IR Filter


// SD-Card (SD_MMC 1-bit mode)
#define SDMMC_CLK_PIN    5
#define SDMMC_CMD_PIN    4
#define SDMMC_DATA_PIN   6

#define PCIE_PWR_PIN     48
#define PCIE_TX_PIN      45
#define PCIE_RX_PIN      46
#define PCIE_LED_PIN     21
#define MIC_IIS_WS_PIN   42
#define MIC_IIS_SCK_PIN  41
#define MIC_IIS_DATA_PIN 2

// Camera Pins
#define CAM_PWDN_PIN     -1
#define CAM_RESET_PIN    -1
#define CAM_XCLK_PIN     34
#define CAM_SIOD_PIN     15
#define CAM_SIOC_PIN     16
#define CAM_Y9_PIN       14
#define CAM_Y8_PIN       13
#define CAM_Y7_PIN       12
#define CAM_Y6_PIN       11
#define CAM_Y5_PIN       10
#define CAM_Y4_PIN       9
#define CAM_Y3_PIN       8
#define CAM_Y2_PIN       7
#define CAM_VSYNC_PIN    36
#define CAM_HREF_PIN     35
#define CAM_PCLK_PIN     37


// #define PWDN_GPIO_NUM  -1
// #define RESET_GPIO_NUM -1
// #define XCLK_GPIO_NUM  39
// #define SIOD_GPIO_NUM  15
// #define SIOC_GPIO_NUM  16











#define BUTTON_PIN       0
#define PWR_ON_PIN       1
#define SERIAL_RX_PIN    44
#define SERIAL_TX_PIN    43
#define BAT_VOLT_PIN     -1

#endif
