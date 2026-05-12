from run_pipeline import PipelineStep, should_use_cache


def test_rerun_from_match_uses_cache_for_upstream_steps_only() -> None:
    assert should_use_cache(step=PipelineStep.SCRIPT, rerun_from=PipelineStep.MATCH)
    assert should_use_cache(step=PipelineStep.VLM, rerun_from=PipelineStep.MATCH)
    assert should_use_cache(step=PipelineStep.TTS, rerun_from=PipelineStep.MATCH)
    assert should_use_cache(step=PipelineStep.WHISPER, rerun_from=PipelineStep.MATCH)
    assert should_use_cache(step=PipelineStep.SENTENCE_LEDGER, rerun_from=PipelineStep.MATCH)
    assert not should_use_cache(step=PipelineStep.MATCH, rerun_from=PipelineStep.MATCH)
    assert not should_use_cache(step=PipelineStep.ASSEMBLE, rerun_from=PipelineStep.MATCH)
    assert not should_use_cache(step=PipelineStep.RENDER, rerun_from=PipelineStep.MATCH)


def test_rerun_from_tts_bypasses_cache_from_tts_onward() -> None:
    assert should_use_cache(step=PipelineStep.SCRIPT, rerun_from=PipelineStep.TTS)
    assert should_use_cache(step=PipelineStep.VLM, rerun_from=PipelineStep.TTS)
    assert not should_use_cache(step=PipelineStep.TTS, rerun_from=PipelineStep.TTS)
    assert not should_use_cache(step=PipelineStep.WHISPER, rerun_from=PipelineStep.TTS)
    assert not should_use_cache(step=PipelineStep.SENTENCE_LEDGER, rerun_from=PipelineStep.TTS)
    assert not should_use_cache(step=PipelineStep.MATCH, rerun_from=PipelineStep.TTS)
