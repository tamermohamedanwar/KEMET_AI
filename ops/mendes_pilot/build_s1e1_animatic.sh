#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="/data/data/com.termux/files/home/products/Kemet_AI"
OUT="$ROOT/ops/mendes_pilot/artifacts/s1e1_blue_ring_controlled_pilot.mp4"
TMP="$ROOT/ops/mendes_pilot/.build_s1e1"
mkdir -p "$TMP" "$(dirname "$OUT")"
rm -f "$OUT" "$TMP/pilot.srt" "$TMP/bed.m4a"

cat > "$TMP/pilot.srt" <<'EOF'
1
00:00:00,000 --> 00:00:15,000
الحلقة 1 — الخاتم الأزرق
يونس يلتقط خاتمًا أزرق من بين حجارة قديمة.

2
00:00:15,000 --> 00:00:30,000
علامة منسية
آمنة تحذره: الحاجة اللي مش عارفين أصلها، ما ناخدهاش معانا.

3
00:00:30,000 --> 00:00:45,000
حين يضيء الخاتم
الخاتم يدفأ في يد يونس عندما يلمسه ضوء القمر.

4
00:00:45,000 --> 00:01:00,000
الصوت خلف الجدار
صوت معدني خافت يقود يونس وآمنة إلى علامة على الجدار.

5
00:01:00,000 --> 00:01:15,000
الباب يتحرك
يونس يضع الخاتم أمام العلامة، فيتحرك جزء صغير من الجدار.

6
00:01:15,000 --> 00:01:30,000
النهاية التي تفتح السؤال
ضوء أزرق يكشف علامة جديدة... لكن ما وراءها يبقى مجهولًا.

7
00:00:04,000 --> 00:01:29,000
Hikayat Mendes • Mendes World • Fictional Story • Original Content

8
00:01:16,000 --> 00:01:29,000
Controlled Pilot • Human Approval Required • Rights Review Required
EOF
ffmpeg -y -hide_banner -loglevel error -f lavfi -i "color=c=0x0b1220:s=1280x720:r=15:d=90" \
  -vf "drawbox=x=70:y=70:w=1140:h=580:color=0x163a5f@0.55:t=12,drawbox=x=100:y=100:w=1080:h=520:color=black@0.18:t=fill,subtitles=$TMP/pilot.srt" \
  -an -c:v libx264 -preset ultrafast -crf 24 -pix_fmt yuv420p "$TMP/video.mp4"

ffmpeg -y -hide_banner -loglevel error -f lavfi -i "anullsrc=r=48000:cl=stereo:d=90" -c:a aac -b:a 96k "$TMP/bed.m4a"

ffmpeg -y -hide_banner -loglevel error -i "$TMP/video.mp4" -i "$TMP/bed.m4a" \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 96k -shortest "$OUT"

ffprobe -v error -show_entries format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate \
  -of default=noprint_wrappers=1 "$OUT"
printf "ARTIFACT=%s\n" "$OUT"
