#!/data/data/com.termux/files/usr/bin/bash
cd ~/products/Kemet_AI
export PIPER_VOICE_PATH=$PWD/.kemet_runtime/piper/voices
piper -m ar_JO-kareem-medium -i ops/commercial_video/commercial_v2/voice_script_ar_v2.txt -f ops/commercial_video/commercial_v2/test_voice.wav
