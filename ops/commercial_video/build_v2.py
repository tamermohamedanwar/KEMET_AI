from pathlib import Path
import subprocess, hashlib, json, os
R=Path.home()/'products/Kemet_AI'; O=R/'ops/commercial_video/commercial_v2'; S=O/'scenes'
S.mkdir(parents=True,exist_ok=True)
FONT='/system/fonts/NotoSansArabic-Regular.ttf'
FONTB='/system/fonts/NotoNaskhArabic-Bold.ttf'
sc=[('THE PROBLEM','Your business is moving. Your tools are not.','#0a0c18'),('ONE COMMAND CENTER','One place to understand what matters next.','#120e22'),('FROM IDEA TO OUTPUT','Plan. Create. Review. Keep the work connected.','#0c1620'),('REAL BUSINESS WORK','Content, decisions, follow-up, execution.','#140e20'),('YOU STAY IN CONTROL','Important actions wait for your approval.','#0a1819'),('BUILT FOR REVENUE','Turn work into offers, campaigns and measurable leads.','#16101c'),('MEASURE WHAT MOVES','See outcomes. Learn. Improve the next move.','#0c121e'),('KEMET','Run your business with Kemet.','#080a12')]
voice='''كل يوم، شغلك بيتوزع بين أدوات ورسائل وملفات وقرارات. المشكلة مش إنك محتاج أداة جديدة. المشكلة إن الشغل نفسه مش متصل. هنا يأتي Kemet. مركز واحد يفهم ما يحدث، يخطط للخطوة التالية، ويربط العمل من الفكرة إلى التنفيذ. من المحتوى والعروض، إلى المتابعة والقرارات وقياس النتائج. والأهم: أنت صاحب القرار. الإجراءات المهمة لا تتحرك بدون موافقتك. Kemet يحول أدواتك المتفرقة إلى منظومة عمل واحدة، مصممة لتساعدك على الوصول إلى نتيجة تجارية حقيقية. لا تستخدم أداة AI أخرى. أدر عملك مع Kemet.'''
V=O/'voice_ar.wav'; OUT=O/'Kemet_Commercial_V2.mp4'
subprocess.run(['espeak-ng','-v','ar','-s','142','-p','48','-a','190','-w',str(V)],input=voice.encode(),check=True)
for i,(title,sub,bg) in enumerate(sc,1):
    p=S/f'{i:02d}.mp4'; esc=lambda x:x.replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
    if i in (2,3,4,6,7):
        boxes="drawbox=x=1080:y=180:w=650:h=690:color=white@0.07:t=2,drawbox=x=1130:y=230:w=550:h=90:color=white@0.09:t=0,drawbox=x=1130:y=350:w=250:h=420:color=white@0.06:t=0,drawbox=x=1400:y=350:w=280:h=190:color=white@0.06:t=0"
    elif i==5:
        boxes="drawbox=x=1030:y=210:w=720:h=520:color=white@0.06:t=2,drawbox=x=1090:y=275:w=600:h=92:color=white@0.09:t=0,drawbox=x=1090:y=410:w=600:h=230:color=white@0.04:t=0"
    else:
        boxes="drawbox=x=1030:y=190:w=720:h=610:color=white@0.05:t=2"
    vf=f"{boxes},drawtext=fontfile={FONTB}:text='{esc(title)}':fontcolor=white:fontsize=64:x=110:y=145,drawtext=fontfile={FONT}:text='{esc(sub)}':fontcolor=white@0.82:fontsize=38:x=110:y=270:enable='between(t,0.5,5.8)',drawtext=fontfile={FONTB}:text='KEMET':fontcolor=white@0.55:fontsize=30:x=110:y=930,drawtext=fontfile={FONT}:text='{i:02d}':fontcolor=white@0.3:fontsize=28:x=1770:y=930"
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i',f'color=c={bg}:s=1920x1080:r=30','-t','6','-vf',vf,'-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-an',str(p)],check=True)
cat=O/'concat.txt'; cat.write_text(''.join(f"file '{p.as_posix()}'\n" for p in sorted(S.glob('*.mp4'))),encoding='utf8')
vid=O/'video.mp4'; subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(cat),'-c','copy',str(vid)],check=True)
# clean, non-bass ambient layer
final=O/'final.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(vid),'-i',str(V),'-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=48','-filter_complex','[2:a]volume=0.008,afade=t=in:st=0:d=3,afade=t=out:st=44:d=4[p];[1:a]volume=1.35,aresample=48000[vo];[vo][p]amix=inputs=2:duration=first:dropout_transition=2[a]','-map','0:v','-map','[a]','-c:v','copy','-c:a','aac','-b:a','192k','-shortest',str(final)],check=True)
os.replace(final,OUT)
h=hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest={'schema':'kemet.commercial.video.v2','artifact':str(OUT.relative_to(R)),'sha256':h,'duration_target_seconds':48,'resolution':'1920x1080','scenes':len(sc),'voice':'piper ar_JO-kareem-medium','music':'subtle 440Hz ambient, no bass','mcp':False,'publication':'REVIEW_REQUIRED','human_approval_required':True}
(O/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'ok':True,'artifact':str(OUT),'sha256':h},ensure_ascii=False))
