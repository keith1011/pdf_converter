from ocr_pipeline.dse_mcq_profile import default_math_cp_p2_path, load_mcq_profile


def test_load_math_cp_p2_profile():
    path = default_math_cp_p2_path()
    assert path.is_file()
    p = load_mcq_profile(path)
    assert p.id == "math_cp_p2"
    assert p.dual_column is False
    assert p.min_option_hits == 3
    assert p.left_bias_ratio == 0.25
    assert len(p.stem_opener_patterns) >= 1
    assert "A" in p.option_letters
    assert p.question_id_min == 1
    assert p.question_id_max == 45
    assert p.require_increasing_ids is True
    assert p.drop_incomplete is True
    assert p.recover_orphan_options is True
