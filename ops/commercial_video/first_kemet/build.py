from pathlib import Path
import subprocess, json, hashlib, os, textwrap

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'Kemet_First_Commercial_Video_v1.mp4'
VOICE = ROOT / 'voiceover_ar_eg.wav'
SCENES = ROOT / 'scenes'
SCENES.mkdir(parents=True, exist_ok=True)
FONT = '/system/fonts/NotoNaskhArabic-Bold.ttf'

script = [
    'مشكلتك ليست نقص أدوات. مشكلتك أن أدواتك لا تعمل كمنظومة واحدة.',
    'هنا يأتي Kemet. مكان واحد لفهم عملك، تخطيطه، ومتابعة التنفيذ.',
    'من الفكرة إلى المحتوى: سيناريو، تعليق صوتي، مشاهد، مونتاج، ورسالة بيع واضحة.',
    'وكل خطوة مهمة تمر عبر موافقتك قبل أي إجراء خارجي.',
    'ابدأ بعرض تجاري عملي: فيديو تسويقي جاهز للنشر، مع CTA يقيس اهتمام العملاء.',
    'Kemet — لا تستخدم أداة AI أخرى. أدر عملك مع Kemet. اطلب أول تجربة تجارية الآن.',
]
scene_titles = ['المشكلة','المركز الواحد','من الفكرة إلى الفيديو','أنت صاحب القرار','العرض التجاري','ابدأ الآن']

# Real Arabic voiceover using the installed local speech engine; no external provider.
full_text = ' '.join(script)
subprocess.run(['espeak-ng','-v','ar','-s','145','-p','45','-a','180','-w',str(VOICE),full_text], check=True)

# Each scene is a real rendered video segment with Arabic typography and motion.
for i, (title, text) in enumerate(zip(scene_titles, script), 1):
    safe = text.replace(':','\\:').replace("'", "\\'")
    title_safe = title.replace(':','\\:').replace("'", "\\'")
    scene = SCENES / f'scene_{i:02d}.mp4'
    vf = (
        f"drawbox=x=70:y=70:w=1140:h=580:color=white@0.08:t=2,"
        f"drawtext=fontfile={FONT}:text='{title_safe}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=125,"
        f"drawtext=fontfile={FONT}:text='{safe}':fontcolor=white:fontsize=40:line_spacing=18:" 
        f"x=100:y=(h-text_h)/2-10:box=1:boxcolor=black@0.18:boxborderw=26,"
        f"drawtext=fontfile={FONT}:text='KEMET':fontcolor=white@0.55:fontsize=28:x=90:y=665"
    )
    bg = ['#0b1020','#101b3d','#152a45','#1c2340','#132d28','#24162f'][i-1]
    subprocess.run([
        'ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi',
        '-i',f'color=c={bg}:s=1280x720:r=30','-t','6',
        '-vf',vf,'-c:v','libx264','-pix_fmt','yuv420p','-an',str(scene)
    ], check=True)

concat = ROOT / 'concat.txt'
concat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in sorted(SCENES.glob('scene_*.mp4'))), encoding='utf-8')
video_only = ROOT / 'video_only.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-c','copy',str(video_only)], check=True)

# Low-volume generated ambient bed keeps the commercial from feeling like a test clip.
final = ROOT / 'final_tmp.mp4'
subprocess.run([
    'ffmpeg','-hide_banner','-loglevel','error','-y',
    '-i',str(video_only),'-i',str(VOICE),
    '-f','lavfi','-t','36','-i','sine=frequency=196:sample_rate=48000',
    '-filter_complex','[2:a]volume=0.035,afade=t=in:st=0:d=2,afade=t=out:st=32:d=4[bed];[1:a]volume=1.25,aresample=48000[vo];[vo][bed]amix=inputs=2:duration=first:dropout_transition=2[a]',
    '-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','160k','-shortest',str(final)
], check=True)
os.replace(final, OUT)

# Build a machine-readable evidence manifest for review and approval.
def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

manifest = {
    'schema':'kemet.commercial.video.v1',
    'artifact': OUT.name,
    'artifact_digest': digest(OUT),
    'duration_seconds': 36,
    'resolution':'1280x720',
    'audio':'local_arabic_espeak_ng',
    'voice_external_provider': False,
    'scenes': [{'index':i,'title':t,'message':s,'duration_seconds':6} for i,(t,s) in enumerate(zip(scene_titles,script),1)],
    'commercial_offer': {
        'name':'Kemet Commercial Launch Video',
        'deliverable':'marketing video with CTA and measurable lead path',
        'cta':'اطلب أول تجربة تجارية الآن',
        'price':'not set; requires human-approved commercial terms'
    },
    'governance': {
        'status':'REVIEW_REQUIRED',
        'human_approval_required':True,
        'publication_requested':False,
        'external_execution':False,
        'mcp':False
    }
}
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'success':True,'video':str(OUT),'voice':str(VOICE),'digest':manifest['artifact_digest']},ensure_ascii=False))
