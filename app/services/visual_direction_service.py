"""Kemet-native visual direction intelligence for the unified command surface."""
from __future__ import annotations
from typing import Any


class VisualDirectionService:
    VERSION = "1.2"
    PRODUCTION_PROFILES = {
        "cinematic": {"story_grammar": "visual_narrative", "shot_grammar": "cinematic_coverage", "camera_language": "controlled_cinematic", "pacing": "intentional", "asset_strategy": "reference_first", "character_strategy": "identity_locked", "world_strategy": "continuity_locked", "voice_strategy": "narrated_or_dialogue", "sound_strategy": "music_ambience_sfx", "editorial_strategy": "shot_to_timeline", "qa_rules": ["continuity", "composition", "typography", "audio_sync"], "output_rules": ["master_video", "playable_artifact"]},
        "commercial": {"story_grammar": "problem_value_outcome", "shot_grammar": "hero_product_coverage", "camera_language": "premium_brand", "pacing": "high_clarity", "asset_strategy": "brand_first", "character_strategy": "purpose_driven", "world_strategy": "brand_consistent", "voice_strategy": "brand_voice", "sound_strategy": "music_sfx", "editorial_strategy": "message_first", "qa_rules": ["brand_consistency", "cta_clarity", "typography", "audio_sync"], "output_rules": ["master_video", "social_derivatives"]},
        "documentary": {"story_grammar": "evidence_led", "shot_grammar": "observational", "camera_language": "naturalistic", "pacing": "editorial", "asset_strategy": "source_trace", "character_strategy": "subject_consistency", "world_strategy": "location_consistency", "voice_strategy": "clear_narration", "sound_strategy": "natural_ambience", "editorial_strategy": "evidence_timeline", "qa_rules": ["source_trace", "continuity", "audio_clarity"], "output_rules": ["master_video"]},
        "educational": {"story_grammar": "concept_to_explanation", "shot_grammar": "demonstration", "camera_language": "clarity_first", "pacing": "instructional", "asset_strategy": "diagram_and_example", "character_strategy": "instructor_or_object", "world_strategy": "contextual", "voice_strategy": "clear_narration", "sound_strategy": "light_sfx", "editorial_strategy": "learning_sequence", "qa_rules": ["factual_clarity", "readability", "audio_clarity"], "output_rules": ["master_video", "caption_ready"]},
        "explainer": {"story_grammar": "problem_to_solution", "shot_grammar": "information_sequence", "camera_language": "graphic_clarity", "pacing": "fast_clear", "asset_strategy": "visual_explanation", "character_strategy": "optional", "world_strategy": "concept_space", "voice_strategy": "narration", "sound_strategy": "minimal_sfx", "editorial_strategy": "information_first", "qa_rules": ["readability", "message_clarity", "audio_sync"], "output_rules": ["master_video", "social_derivatives"]},
        "cartoon": {"story_grammar": "character_story", "shot_grammar": "expressive_coverage", "camera_language": "storybook_dynamic", "pacing": "character_timing", "asset_strategy": "character_reference", "character_strategy": "identity_locked", "world_strategy": "style_locked", "voice_strategy": "character_voice", "sound_strategy": "music_sfx", "editorial_strategy": "performance_first", "qa_rules": ["character_identity", "style_consistency", "continuity", "audio_sync"], "output_rules": ["master_video"]},
        "animation": {"story_grammar": "animated_narrative", "shot_grammar": "pose_and_motion", "camera_language": "animated_camera", "pacing": "motion_timing", "asset_strategy": "pose_reference", "character_strategy": "identity_locked", "world_strategy": "style_locked", "voice_strategy": "dialogue_or_narration", "sound_strategy": "music_foley_sfx", "editorial_strategy": "animation_timeline", "qa_rules": ["motion", "timing", "identity", "continuity"], "output_rules": ["master_video"]},
        "3d_stylized": {"story_grammar": "stylized_narrative", "shot_grammar": "3d_coverage", "camera_language": "virtual_camera", "pacing": "cinematic", "asset_strategy": "3d_reference", "character_strategy": "identity_locked", "world_strategy": "style_locked", "voice_strategy": "narration_or_dialogue", "sound_strategy": "music_sfx", "editorial_strategy": "timeline_first", "qa_rules": ["style_consistency", "continuity", "composition"], "output_rules": ["master_video"]},
        "motion_graphics": {"story_grammar": "information_design", "shot_grammar": "graphic_sequence", "camera_language": "2_5d_motion", "pacing": "kinetic", "asset_strategy": "deterministic_graphics", "character_strategy": "optional", "world_strategy": "brand_grid", "voice_strategy": "voiceover", "sound_strategy": "beat_sfx", "editorial_strategy": "keyframe_timeline", "qa_rules": ["typography", "layout", "animation_timing", "arabic_text"], "output_rules": ["master_video", "transparent_assets_when_supported"]},
        "social_short": {"story_grammar": "hook_value_cta", "shot_grammar": "short_form_coverage", "camera_language": "mobile_first", "pacing": "high_retention", "asset_strategy": "fast_reference", "character_strategy": "identity_if_reused", "world_strategy": "platform_native", "voice_strategy": "clear_shortform", "sound_strategy": "music_sfx", "editorial_strategy": "vertical_first", "qa_rules": ["hook_clarity", "readability", "audio_sync"], "output_rules": ["vertical_master", "caption_ready"]},
        "product_film": {"story_grammar": "product_value", "shot_grammar": "product_hero_macro", "camera_language": "premium_product", "pacing": "precise", "asset_strategy": "product_reference", "character_strategy": "optional", "world_strategy": "brand_consistent", "voice_strategy": "optional_narration", "sound_strategy": "music_sfx", "editorial_strategy": "product_reveal", "qa_rules": ["product_accuracy", "brand_consistency", "typography"], "output_rules": ["master_video"]},
        "corporate_film": {"story_grammar": "mission_people_outcomes", "shot_grammar": "executive_documentary", "camera_language": "premium_realism", "pacing": "confident", "asset_strategy": "brand_and_people", "character_strategy": "identity_consistent", "world_strategy": "real_world_consistency", "voice_strategy": "corporate_narration", "sound_strategy": "music_ambience", "editorial_strategy": "message_led", "qa_rules": ["brand_consistency", "message_clarity", "audio_clarity"], "output_rules": ["master_video"]},
        "story_narrative": {"story_grammar": "character_arc", "shot_grammar": "narrative_coverage", "camera_language": "story_driven", "pacing": "dramatic", "asset_strategy": "character_world_reference", "character_strategy": "identity_locked", "world_strategy": "continuity_locked", "voice_strategy": "dialogue_or_narration", "sound_strategy": "music_ambience_foley", "editorial_strategy": "dramatic_timeline", "qa_rules": ["continuity", "identity", "audio_sync", "story_clarity"], "output_rules": ["master_video"]},
        "news_informative": {"story_grammar": "fact_context_update", "shot_grammar": "information_coverage", "camera_language": "clear_editorial", "pacing": "timely", "asset_strategy": "source_trace", "character_strategy": "optional", "world_strategy": "contextual", "voice_strategy": "clear_narration", "sound_strategy": "minimal", "editorial_strategy": "fact_first", "qa_rules": ["source_trace", "fact_labeling", "readability", "audio_clarity"], "output_rules": ["master_video", "caption_ready"]},
        "photoreal": {"story_grammar": "single_visual", "shot_grammar": "hero_composition", "camera_language": "photoreal_controlled", "pacing": "static_or_sequence", "asset_strategy": "reference_first", "character_strategy": "identity_if_present", "world_strategy": "location_consistent", "voice_strategy": "optional", "sound_strategy": "optional", "editorial_strategy": "image_first", "qa_rules": ["composition", "identity", "brand_consistency"], "output_rules": ["master_image", "social_derivatives"]},
        "social_post": {"story_grammar": "hook_value_cta", "shot_grammar": "graphic_or_text", "camera_language": "none", "pacing": "scan_first", "asset_strategy": "brand_reference", "character_strategy": "optional", "world_strategy": "brand_consistent", "voice_strategy": "none", "sound_strategy": "none", "editorial_strategy": "message_first", "qa_rules": ["readability", "cta_clarity", "brand_consistency"], "output_rules": ["post_ready"]},
        "long_form": {"story_grammar": "multi_sequence_narrative", "shot_grammar": "sequence_coverage", "camera_language": "story_driven", "pacing": "chaptered", "asset_strategy": "reference_first", "character_strategy": "identity_locked", "world_strategy": "continuity_locked", "voice_strategy": "narration_or_dialogue", "sound_strategy": "music_ambience_foley", "editorial_strategy": "chapter_timeline", "qa_rules": ["continuity", "identity", "audio_clarity", "story_clarity"], "output_rules": ["master_video", "chapter_derivatives"]},
        "custom": {"story_grammar": "intent_driven", "shot_grammar": "output_specific", "camera_language": "not_applicable", "pacing": "intentional", "asset_strategy": "requirement_first", "character_strategy": "optional", "world_strategy": "optional", "voice_strategy": "language_and_dialect_bound", "sound_strategy": "requirement_driven", "editorial_strategy": "artifact_first", "qa_rules": ["requirement_compliance", "readability", "audio_clarity"], "output_rules": ["canonical_artifact"]},
    }
    CATALOG = {
        "cinematic": {"label": "Cinematic", "ar": "سينمائي", "description": "لغة فيلمية، كاميرا وإضاءة وعمق بصري.", "accent": "film"},
        "animation": {"label": "Animation", "ar": "رسوم متحركة", "description": "حركة مرنة وبناء بصري متكامل للشخصيات والمشاهد.", "accent": "motion"},
        "cartoon": {"label": "Cartoon", "ar": "كرتوني", "description": "شخصيات كرتونية وهوية بصرية واضحة ومعبّرة.", "accent": "toon"},
        "motion_graphics": {"label": "Motion Graphics", "ar": "موشن جرافيكس", "description": "Typography وحركة وعناصر بصرية للمحتوى والعلامات التجارية.", "accent": "motion"},
        "photoreal": {"label": "Photoreal", "ar": "واقعي", "description": "واقعية عالية مع ضبط الضوء والخامة والتفاصيل.", "accent": "real"},
        "stylized": {"label": "Stylized", "ar": "أسلوب فني", "description": "هوية فنية مميزة قابلة للتخصيص والمرجعية.", "accent": "art"},
        "educational": {"label": "Educational", "ar": "تعليمي", "description": "شرح بصري واضح، معلومات منظمة، وإيقاع يخدم الفهم.", "accent": "learn"},
        "commercial": {"label": "Commercial", "ar": "تجاري", "description": "سرد تجاري يربط الفكرة بالعلامة والدعوة إلى الإجراء.", "accent": "brand"},
        "custom": {"label": "Custom", "ar": "مخصص", "description": "اتجاه بصري تصفه أنت ويهندسه Kemet.", "accent": "custom"},
    }
    DETAIL_OPTIONS = {
        "cinematic": {
            "visual_language": ["Premium enterprise film", "Dark contrast cinema", "Bright modern technology"],
            "character_direction": ["Human executive", "Realistic team", "No recurring character"],
            "world_direction": ["Modern headquarters", "Operations floor", "Abstract business space"],
            "camera_direction": ["Controlled dolly", "Locked precision", "Dynamic tracking"],
            "audio_direction": ["Clean narration", "Cinematic score", "Designed business SFX"],
        },
        "animation": {
            "visual_language": ["3D animation", "2D animation", "Hybrid animation"],
            "character_direction": ["Expressive character", "Professional avatar", "Object-led story"],
            "world_direction": ["Designed studio", "Stylized city", "Abstract world"],
            "camera_direction": ["Smooth crane", "Orbit", "Graphic transition"],
            "audio_direction": ["Character voice", "Narrated", "Music-led"],
        },
        "cartoon": {
            "visual_language": ["Premium cartoon", "2D illustrated", "3D stylized"],
            "character_direction": ["Hero character", "Ensemble", "Object characters"],
            "world_direction": ["Clean studio", "Story world", "Playful environment"],
            "camera_direction": ["Storybook framing", "Dynamic push", "Comedic timing"],
            "audio_direction": ["Narrated", "Character dialogue", "Music + SFX"],
        },
        "motion_graphics": {
            "visual_language": ["Editorial typography", "Data-driven", "Brand motion"],
            "character_direction": ["No character", "Silhouette", "Iconic human"],
            "world_direction": ["Clean grid", "Brand space", "Data environment"],
            "camera_direction": ["2.5D push", "Kinetic transitions", "Macro detail"],
            "audio_direction": ["Voiceover", "Beat-driven", "Minimal SFX"],
        },
        "photoreal": {
            "visual_language": ["Naturalistic", "Commercial realism", "Documentary realism"],
            "character_direction": ["Single subject", "Team", "No character"],
            "world_direction": ["Real office", "Real environment", "Location-neutral"],
            "camera_direction": ["Handheld controlled", "Cinematic dolly", "Static composed"],
            "audio_direction": ["Natural sound", "Voiceover", "Music-led"],
        },
        "stylized": {
            "visual_language": ["Editorial art", "Painterly", "Futuristic"],
            "character_direction": ["Hero", "Abstract figure", "No character"],
            "world_direction": ["Surreal", "Graphic world", "Minimal space"],
            "camera_direction": ["Abstract movement", "Precision framing", "Wide reveal"],
            "audio_direction": ["Atmospheric", "Narrated", "Experimental"],
        },
        "educational": {
            "visual_language": ["Explainer film", "Diagram-led", "Story-based learning"],
            "character_direction": ["Instructor", "Learner journey", "Object-led explanation"],
            "world_direction": ["Classroom", "Concept space", "Real-world context"],
            "camera_direction": ["Clear framing", "Demonstration close-up", "Step reveal"],
            "audio_direction": ["Clear narration", "Dialogue", "Light instructional SFX"],
        },
        "commercial": {
            "visual_language": ["Premium brand film", "Product story", "Performance creative"],
            "character_direction": ["Customer journey", "Brand representative", "No recurring character"],
            "world_direction": ["Brand environment", "Customer environment", "Abstract value space"],
            "camera_direction": ["Hero reveal", "Controlled tracking", "Product macro"],
            "audio_direction": ["Brand narration", "Dialogue", "Music + designed SFX"],
        },
        "custom": {
            "visual_language": ["Describe your style"],
            "character_direction": ["Describe your character"],
            "world_direction": ["Describe your world"],
            "camera_direction": ["Describe camera language"],
            "audio_direction": ["Describe voice and sound"],
        },
    }

    def suggest(self, command: str, task_type: str | None = None) -> list[dict[str, Any]]:
        text = str(command or "").lower()
        scores = {key: 0 for key in self.CATALOG}
        if any(x in text for x in ("إعلان", "اعلان", "commercial", "brand", "براند")):
            scores["cinematic"] += 5; scores["motion_graphics"] += 4; scores["photoreal"] += 3
        if any(x in text for x in ("فيلم", "سينما", "cinematic", "مشهد")):
            scores["cinematic"] += 6; scores["photoreal"] += 2; scores["stylized"] += 2
        if any(x in text for x in ("كرتون", "cartoon")):
            scores["cartoon"] += 7; scores["animation"] += 5
        if any(x in text for x in ("رسوم", "animation", "animated")):
            scores["animation"] += 7; scores["cartoon"] += 3
        if any(x in text for x in ("موشن", "motion graphics", "انفوجرافيك", "infographic")):
            scores["motion_graphics"] += 8
        if any(x in text for x in ("واقعي", "واقعية", "photoreal", "realistic")):
            scores["photoreal"] += 7
        if any(x in text for x in ("فني", "stylized", "أسلوب", "style")):
            scores["stylized"] += 5
        if any(x in text for x in ("تعليمي", "تعليم", "educational", "education", "شرح", "درس")):
            scores["educational"] += 8
        if any(x in text for x in ("تجاري", "commercial", "sales", "بيع", "عرض", "cta")):
            scores["commercial"] += 8
        if task_type == "multimodal":
            scores["cinematic"] += 2; scores["photoreal"] += 1; scores["stylized"] += 1
        if max(scores.values()) == 0:
            for key in self.CATALOG: scores[key] = 1
        ranked = sorted(scores, key=lambda key: (-scores[key], list(self.CATALOG).index(key)))
        return [{**self.CATALOG[key], "id": key, "score": scores[key]} for key in ranked]

    def production_profile(self, profile_id: str) -> dict[str, Any]:
        key = str(profile_id or "").strip().lower()
        if key not in self.PRODUCTION_PROFILES:
            raise ValueError("unsupported_production_profile")
        contract = {"schema": "kemet.production_profile.v1", "version": 1, "profile_id": key, **self.PRODUCTION_PROFILES[key], "provider_independent": True, "planning_only": True}
        from hashlib import sha256
        import json
        contract["digest"] = sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        return contract

    def production_profiles(self) -> list[dict[str, Any]]:
        return [self.production_profile(key) for key in self.PRODUCTION_PROFILES]

    def details(self, direction_id: str) -> dict[str, Any]:
        key = str(direction_id or "").strip()
        if key not in self.CATALOG:
            raise ValueError("invalid_visual_direction")
        return {"direction": {**self.CATALOG[key], "id": key}, "options": self.DETAIL_OPTIONS[key]}

    def compile_profile(self, direction_id: str, *, task_type: str | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        key = str(direction_id or "").strip()
        if key not in self.CATALOG:
            raise ValueError("invalid_visual_direction")
        profiles = {
            "cinematic": {"first_class_assets": ["characters", "environments", "camera", "lighting", "audio"], "qa_dimensions": ["camera", "lighting", "realism", "continuity"]},
            "cartoon": {"first_class_assets": ["characters", "environments", "wardrobe", "props", "animation"], "qa_dimensions": ["character_identity", "proportions", "style_consistency", "continuity"]},
            "animation": {"first_class_assets": ["characters", "key_poses", "expressions", "motion", "camera"], "qa_dimensions": ["motion", "timing", "poses", "expressions", "continuity"]},
            "motion_graphics": {"first_class_assets": ["typography", "ui", "icons", "diagrams", "transitions", "data_visualization"], "qa_dimensions": ["typography", "layout", "hierarchy", "animation_timing"]},
            "photoreal": {"first_class_assets": ["subjects", "locations", "camera", "lighting", "materials"], "qa_dimensions": ["realism", "lighting", "camera", "continuity"]},
            "stylized": {"first_class_assets": ["style_language", "characters", "environments", "composition", "color_language"], "qa_dimensions": ["style_consistency", "composition", "continuity", "reference_compliance"]},
            "educational": {"first_class_assets": ["explanations", "diagrams", "examples", "typography", "narration"], "qa_dimensions": ["factual_clarity", "readability", "instructional_pacing", "audio_clarity"]},
            "commercial": {"first_class_assets": ["brand_identity", "product", "customer_story", "cta", "music_sfx"], "qa_dimensions": ["brand_consistency", "message_clarity", "cta_clarity", "pacing"]},
            "custom": {"first_class_assets": ["style_language", "characters", "environments", "camera", "audio"], "qa_dimensions": ["reference_compliance", "continuity", "composition", "custom_constraints"]},
        }
        base = profiles[key]
        result = {
            "schema": "kemet.visual.production_profile.v1",
            "version": 1,
            "profile_id": key,
            "profile": dict(self.CATALOG[key]),
            "task_type": task_type,
            "first_class_assets": list(base["first_class_assets"]),
            "qa_dimensions": list(base["qa_dimensions"]),
            "detail_options": dict(self.DETAIL_OPTIONS[key]),
            "overrides": dict(overrides or {}),
            "provider_independent": True,
            "canonical_state_source": "canonical_production_state",
            "prompts_are_derived": True,
            "planning_only": True,
            "governance": {"execution_authority": False, "external_execution": False, "human_approval_required": True, "mcp": False},
        }
        from hashlib import sha256
        import json
        result["digest"] = sha256(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        return result


visual_direction_service = VisualDirectionService()
