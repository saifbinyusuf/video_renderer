import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("png");   // per-frame quality for the alpha channel
Config.setCodec("prores");
Config.setProResProfile("4444");     // ProRes 4444 = real alpha channel, high quality
Config.setPixelFormat("yuva444p10le");
