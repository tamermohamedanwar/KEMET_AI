#!/data/data/com.termux/files/usr/bin/bash
set -e
cd ~/products/Kemet_AI
ROOT=ops/commercial_video/commercial_v2
FONT=/system/fonts/NotoNaskhArabic-Regular.ttf
FONTB=/system/fonts/NotoNaskhArabic-Bold.ttf
ENFONT=/system/fonts/CarroisGothicSC-Regular.ttf
mkdir -p "$ROOT/scenes_v2" "$ROOT/review_v2"
VOICE="$ROOT/voice_ar_v2_master.wav"
ffmpeg -y -i "$VOICE" -filter:a 'atempo=1.2,loudnorm=I=-16:TP=-1.5:LRA=7' -ar 48000 -ac 2 "$ROOT/voice_final.wav" >/dev/null 2>&1
make_scene() {
  n="$1"; title="$2"; sub="$3"; kind="$4"
  case "$kind" in
    1) visual="drawbox=x=170:y=190:w=1580:h=700:color=0xF7F9FC@1:t=fill,drawbox=x=220:y=240:w=520:h=28:color=0x14243A@1:t=fill,drawbox=x=220:y=310:w=1120:h=22:color=0xD9E1EA@1:t=fill,drawbox=x=220:y=365:w=880:h=22:color=0xD9E1EA@1:t=fill,drawbox=x=220:y=450:w=420:h=170:color=0xE8EEF5@1:t=fill,drawbox=x=700:y=450:w=300:h=170:color=0xE8EEF5@1:t=fill,drawbox=x=1060:y=450:w=280:h=170:color=0xE8EEF5@1:t=fill";;
    2) visual="drawbox=x=220:y=220:w=1460:h=640:color=0xF7F9FC@1:t=fill,drawbox=x=260:y=270:w=1380:h=70:color=0xE7EDF5@1:t=fill,drawbox=x=260:y=380:w=410:h=360:color=0xE7EDF5@1:t=fill,drawbox=x=710:y=380:w=930:h=150:color=0xE7EDF5@1:t=fill,drawbox=x=710:y=560:w=440:h=180:color=0xE7EDF5@1:t=fill,drawbox=x=1200:y=560:w=440:h=180:color=0xE7EDF5@1:t=fill";;
    3) visual="drawbox=x=230:y=210:w=1480:h=660:color=0xF7F9FC@1:t=fill,drawbox=x=280:y=270:w=420:h=500:color=0xE8EEF5@1:t=fill,drawbox=x=760:y=270:w=900:h=90:color=0x14243A@1:t=fill,drawbox=x=760:y=400:w=900:h=60:color=0xD9E1EA@1:t=fill,drawbox=x=760:y=500:w=700:h=60:color=0xD9E1EA@1:t=fill,drawbox=x=760:y=600:w=520:h=60:color=0xD9E1EA@1:t=fill";;
    4) visual="drawbox=x=200:y=180:w=1520:h=720:color=0xF7F9FC@1:t=fill,drawbox=x=250:y=240:w=1420:h=90:color=0xE8EEF5@1:t=fill,drawbox=x=250:y=380:w=1420:h=420:color=0xE8EEF5@1:t=fill,drawbox=x=310:y=450:w=1200:h=18:color=0xAFC1D5@1:t=fill,drawbox=x=310:y=510:w=1000:h=18:color=0xAFC1D5@1:t=fill,drawbox=x=310:y=570:w=760:h=18:color=0xAFC1D5@1:t=fill";;
    5) visual="drawbox=x=220:y=210:w=1480:h=660:color=0xF7F9FC@1:t=fill,drawbox=x=270:y=270:w=360:h=510:color=0xE8EEF5@1:t=fill,drawbox=x=680:y=270:w=980:h=100:color=0xE8EEF5@1:t=fill,drawbox=x=680:y=420:w=980:h=80:color=0xE8EEF5@1:t=fill,drawbox=x=680:y=550:w=680:h=80:color=0xE8EEF5@1:t=fill,drawbox=x=680:y=680:w=500:h=80:color=0xE8EEF5@1:t=fill";;
    6) visual="drawbox=x=180:y=170:w=1560:h=740:color=0xF7F9FC@1:t=fill,drawbox=x=240:y=240:w=1480:h=80:color=0xE8EEF5@1:t=fill,drawbox=x=240:y=370:w=700:h=430:color=0xE8EEF5@1:t=fill,drawbox=x=1000:y=370:w=660:h=180:color=0xE8EEF5@1:t=fill,drawbox=x=1000:y=600:w=660:h=200:color=0xE8EEF5@1:t=fill";;
    7) visual="drawbox=x=180:y=180:w=1560:h=720:color=0xF7F9FC@1:t=fill,drawbox=x=240:y=240:w=1480:h=70:color=0x14243A@1:t=fill,drawbox=x=240:y=350:w=440:h=420:color=0xE8EEF5@1:t=fill,drawbox=x=740:y=350:w=440:h=420:color=0xE8EEF5@1:t=fill,drawbox=x=1240:y=350:w=420:h=420:color=0xE8EEF5@1:t=fill";;
    8) visual="drawbox=x=260:y=250:w=1400:h=560:color=0xF7F9FC@1:t=fill,drawbox=x=360:y=350:w=1200:h=10:color=0x14243A@1:t=fill,drawbox=x=360:y=430:w=900:h=10:color=0xAFC1D5@1:t=fill,drawbox=x=360:y=510:w=1050:h=10:color=0xAFC1D5@1:t=fill";;
  esac
  ffmpeg -y -f lavfi -i "color=c=0x07111F:s=1920x1080:r=30:d=6" -vf "${visual},drawtext=fontfile=${ENFONT}:text='KEMET AI BOS':fontcolor=white:fontsize=34:x=110:y=82,drawtext=fontfile=${FONTB}:text='${title}':fontcolor=0xFFFFFF:fontsize=62:x=(w-text_w)/2:y=865:text_shaping=1,drawtext=fontfile=${FONT}:text='${sub}':fontcolor=0xB9C7D8:fontsize=34:x=(w-text_w)/2:y=945:text_shaping=1,drawbox=x='120+120*t':y=1040:w=280:h=4:color=0x64D8FF@0.9:t=fill" -an -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$ROOT/scenes_v2/$(printf '%02d' "$n").mp4" >/dev/null 2>&1
}
make_scene 1 'فيه مشكلة أكبر من كثرة الأدوات' 'الصورة الكاملة تضيع بين الرسائل والمهام والقرارات' 1
make_scene 2 'كيمت يجمع الصورة' 'مركز تحكم واحد لفهم العمل والقرارات والنتائج' 2
make_scene 3 'ابدأ بطلب واضح' 'حوّل الهدف إلى خطة قابلة للمراجعة قبل التنفيذ' 3
make_scene 4 'أنت صاحب القرار' 'لا إجراء مؤثر بدون موافقتك' 4
make_scene 5 'نفّذ ثم راجع' 'كل خطوة ونتيجتها وتكلفتها تصبح قابلة للتتبع' 5
make_scene 6 'حوّل النتائج إلى معرفة' 'تعرف ما الذي نجح وما الذي يحتاج إلى تحسين' 6
make_scene 7 'من الحملات إلى الإيرادات' 'ابنِ حلقة عمل تقيس الأثر وتتعلم من النتائج' 7
make_scene 8 'شغّل عملك مع كيمت' 'Run your business with Kemet.' 8
printf "file '$ROOT/scenes_v2/01.mp4'\nfile '$ROOT/scenes_v2/02.mp4'\nfile '$ROOT/scenes_v2/03.mp4'\nfile '$ROOT/scenes_v2/04.mp4'\nfile '$ROOT/scenes_v2/05.mp4'\nfile '$ROOT/scenes_v2/06.mp4'\nfile '$ROOT/scenes_v2/07.mp4'\nfile '$ROOT/scenes_v2/08.mp4'\n" > "$ROOT/concat_v2.txt"
ffmpeg -y -f concat -safe 0 -i "$ROOT/concat_v2.txt" -i "$ROOT/voice_final.wav" -filter_complex "[1:a]adelay=300|300,volume=1.0[a]" -map 0:v -map '[a]' -c:v copy -c:a aac -b:a 192k -shortest "$ROOT/Kemet_Commercial_V2_FINAL.mp4" >/dev/null 2>&1
ffmpeg -y -i "$ROOT/Kemet_Commercial_V2_FINAL.mp4" -vf "select='eq(n,30)+eq(n,330)+eq(n,630)+eq(n,930)+eq(n,1230)'" -vsync vfr "$ROOT/review_v2/frame_%02d.jpg" >/dev/null 2>&1
cp "$ROOT/Kemet_Commercial_V2_FINAL.mp4" ops/youtube_queue/Kemet_Commercial_V2_FINAL.mp4
cp "$ROOT/Kemet_Commercial_V2_FINAL.mp4" "$HOME/storage/downloads/Kemet_Commercial_V2_FINAL.mp4" 2>/dev/null || true
sha256sum "$ROOT/Kemet_Commercial_V2_FINAL.mp4"
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height,sample_rate,channels -of default=noprint_wrappers=1 "$ROOT/Kemet_Commercial_V2_FINAL.mp4"
