"""Stable capability vocabulary used by media routing and planning."""
MEDIA_CAPABILITIES=("TEXT_GENERATION","IMAGE_GENERATION","VIDEO_GENERATION","IMAGE_TO_VIDEO","TEXT_TO_VIDEO","CHARACTER_ANIMATION","VOICE_SYNTHESIS","SOUND_GENERATION","MUSIC_GENERATION","UPSCALE","FRAME_INTERPOLATION","TRANSCRIPTION","TRANSLATION","SUBTITLE_GENERATION","PROCEDURAL_VIDEO_GENERATION","SPEECH_TO_TEXT","TEXT_TO_SPEECH","VOICE","SOUND_EFFECT","MUSIC","DUBBING","VIDEO_UNDERSTANDING","IMAGE_UNDERSTANDING","MEDIA_ANALYSIS","COMPOSITING","RENDERING","CAPTIONING","LOCAL_PROCESSING")
def capability_snapshot(capabilities=None)->dict:
    selected=tuple(capabilities or MEDIA_CAPABILITIES); unknown=[x for x in selected if x not in MEDIA_CAPABILITIES]
    if unknown: raise ValueError("unsupported_media_capability")
    return {"version":"1.0","capabilities":list(selected),"execution_authority":False,"mcp":False}
