from ocr_pipeline.dse_mcq_profile import default_math_cp_p2_path, load_mcq_profile
from ocr_pipeline.dse_mcq_region import detect_mcq_regions
from ocr_pipeline.dse_mcq_types import OcrLine

W, H = 1000.0, 2000.0


def _L(text: str, y: float, x1: float = 40.0, x2: float = 800.0, h: float = 30.0) -> OcrLine:
    return OcrLine(text=text, bbox=(x1, y, x2, y + h), page_width=W, page_height=H)


def test_two_questions_with_abcd():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("1. Find the value of x.", 100),
        _L("A. 1", 200),
        _L("B. 2", 240),
        _L("C. 3", 280),
        _L("D. 4", 320),
        _L("2. Which is correct?", 400),
        _L("A. p", 500),
        _L("B. q", 540),
        _L("C. r", 580),
        _L("D. s", 620),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [1, 2]
    assert all(r.anchors.hit_count >= 3 for r in regions)
    assert all(not r.incomplete for r in regions)
    assert regions[0].bbox[3] <= regions[1].bbox[1] + 1


def test_in_stem_decimal_does_not_open():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("1. Compute 1.5 + 2.", 100),
        _L("The answer is 1.5 when x=1.", 140, x1=80.0),
        _L("A. 3", 200),
        _L("B. 4", 240),
        _L("C. 5", 280),
        _L("D. 6", 320),
        _L("2. Next", 400),
        _L("A. a", 500),
        _L("B. b", 540),
        _L("C. c", 580),
        _L("D. d", 620),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [1, 2]


def test_incomplete_when_few_options():
    from dataclasses import replace

    profile = replace(load_mcq_profile(default_math_cp_p2_path()), drop_incomplete=False)
    lines = [
        _L("3. Partial", 100),
        _L("A. only", 200),
        _L("B. two", 240),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert len(regions) == 1
    assert regions[0].incomplete is True
    assert regions[0].anchors.hit_count == 2


def test_drop_incomplete_by_default():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("3. Partial", 100),
        _L("A. only", 200),
        _L("B. two", 240),
    ]
    assert detect_mcq_regions(lines, profile) == []


def test_right_column_opener_rejected_by_left_bias():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("1. Real question", 100, x1=40.0),
        _L("A. 1", 200),
        _L("B. 2", 240),
        _L("C. 3", 280),
        _L("D. 4", 320),
        # Looks like an opener but sits past left_bias_ratio (0.25 * 1000 = 250)
        _L("9. Fake mid-column", 360, x1=400.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [1]


def test_lone_number_and_preamble_stem_text():
    """RapidOCR often emits stem prose before a lone '8.' opener."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("圖中所示為圖像，下列何者正確？", 100, x1=160.0),
        _L("8.", 110, x1=40.0, x2=80.0),
        _L("A.", 200, x1=40.0, x2=80.0),
        _L("a<0", 200, x1=100.0),
        _L("B.", 240, x1=40.0, x2=80.0),
        _L("C.", 280, x1=40.0, x2=80.0),
        _L("D.", 320, x1=40.0, x2=80.0),
        _L("若價增加70%", 400, x1=160.0),
        _L("9.", 410, x1=40.0, x2=80.0),
        _L("A.", 500, x1=40.0, x2=80.0),
        _L("B.", 540, x1=40.0, x2=80.0),
        _L("C.", 580, x1=40.0, x2=80.0),
        _L("D.", 620, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [8, 9]
    assert all(not r.incomplete for r in regions)
    # Preamble stem text is inside Q8 bbox
    assert regions[0].bbox[1] <= 100 + 1


def test_option_d_keeps_same_row_value():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("1. Q", 100),
        _L("A.", 200, x1=40.0, x2=80.0),
        _L("B.", 240, x1=40.0, x2=80.0),
        _L("C.", 280, x1=40.0, x2=80.0),
        _L("D.", 320, x1=40.0, x2=80.0),
        _L("10%", 322, x1=100.0, x2=200.0),
        _L("Next stem text", 400, x1=160.0),
        _L("2.", 410, x1=40.0, x2=80.0),
        _L("A.", 500, x1=40.0, x2=80.0),
        _L("B.", 540, x1=40.0, x2=80.0),
        _L("C.", 580, x1=40.0, x2=80.0),
        _L("D.", 620, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [1, 2]
    assert regions[0].bbox[3] >= 322
    assert regions[1].bbox[1] >= 390


def test_rejects_decimal_zero_opener():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("0.0023456789=", 100, x1=40.0),
        _L("4.", 110, x1=40.0, x2=80.0),
        _L("A.", 200, x1=40.0, x2=80.0),
        _L("B.", 240, x1=40.0, x2=80.0),
        _L("C.", 280, x1=40.0, x2=80.0),
        _L("D.", 320, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [4]


def test_rejects_mid_stem_roman_one_and_keeps_increasing():
    """OCR often turns Roman 'I.' into '1.' between stem and options."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("25.", 100, x1=40.0, x2=80.0),
        _L("1.", 140, x1=80.0, x2=120.0),
        _L("II.", 180, x1=80.0, x2=140.0),
        _L("A.", 220, x1=40.0, x2=80.0),
        _L("B.", 260, x1=40.0, x2=80.0),
        _L("C.", 300, x1=40.0, x2=80.0),
        _L("D.", 340, x1=40.0, x2=80.0),
        _L("26.", 400, x1=40.0, x2=80.0),
        _L("A.", 440, x1=40.0, x2=80.0),
        _L("B.", 480, x1=40.0, x2=80.0),
        _L("C.", 520, x1=40.0, x2=80.0),
        _L("D.", 560, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [25, 26]


def test_recover_orphan_abcd_as_next_qid():
    """When OCR misses '18.', orphan A–D after 17 become question 18."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("17.", 100, x1=40.0, x2=80.0),
        _L("A.", 140, x1=40.0, x2=80.0),
        _L("B.", 180, x1=40.0, x2=80.0),
        _L("C.", 220, x1=40.0, x2=80.0),
        _L("D.", 260, x1=40.0, x2=80.0),
        # figure crumbs
        _L("AB", 300, x1=100.0),
        # orphan options (missing 18.)
        _L("A.", 400, x1=300.0, x2=340.0),
        _L("cos a", 400, x1=100.0),
        _L("B.", 440, x1=300.0, x2=340.0),
        _L("C.", 480, x1=300.0, x2=340.0),
        _L("D.", 520, x1=300.0, x2=340.0),
        _L("19.", 600, x1=40.0, x2=80.0),
        _L("A.", 640, x1=40.0, x2=80.0),
        _L("B.", 680, x1=40.0, x2=80.0),
        _L("C.", 720, x1=40.0, x2=80.0),
        _L("D.", 760, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [17, 18, 19]
    assert all(not r.incomplete for r in regions)
    assert regions[1].bbox[0] <= regions[0].bbox[0]


def test_recover_leading_orphan_abcd_as_previous_qid():
    """A page-leading question can lose its opener while retaining A-D."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("missing opener stem", 100, x1=160.0),
        _L("A.", 200, x1=300.0, x2=340.0),
        _L("B.", 240, x1=300.0, x2=340.0),
        _L("C.", 280, x1=300.0, x2=340.0),
        _L("D.", 320, x1=300.0, x2=340.0),
        _L("5.", 400, x1=40.0, x2=80.0),
        _L("A.", 500, x1=40.0, x2=80.0),
        _L("B.", 540, x1=40.0, x2=80.0),
        _L("C.", 580, x1=40.0, x2=80.0),
        _L("D.", 620, x1=40.0, x2=80.0),
    ]

    regions = detect_mcq_regions(lines, profile)

    assert [r.question_id for r in regions] == [4, 5]
    assert regions[0].orphan is True
    assert regions[0].bbox[0] <= regions[1].bbox[0]
    assert regions[0].bbox[1] <= 40


def test_leading_orphan_top_pad_stops_after_section_header():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("甲部", 20, x1=40.0, x2=100.0, h=30.0),
        _L("missing opener stem", 100, x1=160.0),
        _L("A.", 200, x1=300.0, x2=340.0),
        _L("B.", 240, x1=300.0, x2=340.0),
        _L("C.", 280, x1=300.0, x2=340.0),
        _L("D.", 320, x1=300.0, x2=340.0),
        _L("2.", 400, x1=40.0, x2=80.0),
        _L("A.", 500, x1=40.0, x2=80.0),
        _L("B.", 540, x1=40.0, x2=80.0),
        _L("C.", 580, x1=40.0, x2=80.0),
        _L("D.", 620, x1=40.0, x2=80.0),
    ]

    regions = detect_mcq_regions(lines, profile)

    assert [r.question_id for r in regions] == [1, 2]
    assert 50 <= regions[0].bbox[1] <= 70


def test_increasing_stems_prefers_longer_sequence_over_false_jump():
    """2020 Q8: OCR read Roman ``II.`` as ``11.`` before the real Q9/Q10."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("8.", 100, x1=40.0, x2=80.0),
        _L("11.", 140, x1=80.0, x2=130.0),
        _L("A.", 200, x1=40.0, x2=80.0),
        _L("B.", 240, x1=40.0, x2=80.0),
        _L("C.", 280, x1=40.0, x2=80.0),
        _L("D.", 320, x1=40.0, x2=80.0),
        _L("9.", 400, x1=40.0, x2=80.0),
        _L("A.", 440, x1=40.0, x2=80.0),
        _L("B.", 480, x1=40.0, x2=80.0),
        _L("C.", 520, x1=40.0, x2=80.0),
        _L("D.", 560, x1=40.0, x2=80.0),
        _L("10.", 640, x1=40.0, x2=90.0),
        _L("A.", 680, x1=40.0, x2=80.0),
        _L("B.", 720, x1=40.0, x2=80.0),
        _L("C.", 760, x1=40.0, x2=80.0),
        _L("D.", 800, x1=40.0, x2=80.0),
    ]

    regions = detect_mcq_regions(lines, profile)

    assert [r.question_id for r in regions] == [8, 9, 10]


def test_keep_sequence_backed_incomplete_graph_question():
    """2017 Q31: graph choices may expose fewer than three OCR option anchors."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("31.", 100, x1=40.0, x2=90.0),
        _L("graph and stem", 160, x1=160.0),
        _L("B.", 300, x1=600.0, x2=650.0),
        _L("8^3 + 8^19 =", 590, x1=160.0),
        _L("32.", 600, x1=40.0, x2=90.0),
        _L("A.", 640, x1=40.0, x2=80.0),
        _L("B.", 680, x1=40.0, x2=80.0),
        _L("C.", 720, x1=40.0, x2=80.0),
        _L("D.", 760, x1=40.0, x2=80.0),
    ]

    regions = detect_mcq_regions(lines, profile)

    assert [r.question_id for r in regions] == [31, 32]
    assert regions[0].incomplete is True
    assert regions[0].bbox[3] <= regions[1].bbox[1] + 1
    assert regions[1].bbox[1] <= 600


def test_drop_incomplete_leading_false_opener():
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("2.", 100, x1=40.0, x2=80.0),
        _L("31.", 200, x1=40.0, x2=90.0),
        _L("A.", 300, x1=40.0, x2=80.0),
        _L("B.", 340, x1=40.0, x2=80.0),
        _L("C.", 380, x1=40.0, x2=80.0),
        _L("D.", 420, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [31]


def test_graph_options_b_d_on_right_not_merged_with_prev():
    """2016p2 p4: Q9 graph options put B./D. on the right half of the page."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("8.", 100, x1=40.0, x2=80.0),
        _L("A.", 140, x1=40.0, x2=80.0),
        _L("B.", 180, x1=40.0, x2=80.0),
        _L("C.", 220, x1=40.0, x2=80.0),
        _L("D.", 260, x1=40.0, x2=80.0),
        _L("若-1<a<0，则下列何者可表示圖像?", 400, x1=160.0),
        _L("9.", 410, x1=40.0, x2=80.0),
        _L("B.", 480, x1=900.0, x2=940.0),  # right column graph
        _L("A.", 490, x1=40.0, x2=80.0),
        _L("D.", 700, x1=900.0, x2=940.0),  # right column graph
        # C. often missed by OCR on graphs; A+B+D still ≥ min_option_hits
        _L("10.", 900, x1=40.0, x2=90.0),
        _L("A.", 940, x1=40.0, x2=80.0),
        _L("B.", 980, x1=40.0, x2=80.0),
        _L("C.", 1020, x1=40.0, x2=80.0),
        _L("D.", 1060, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [8, 9, 10]
    assert regions[0].bbox[3] < regions[1].bbox[1] + 5
    assert regions[1].anchors.A and regions[1].anchors.B and regions[1].anchors.D


def test_formula_ocr_junk_not_stem_opener():
    """2012p2 p2: denominator 2x^5 OCR'd as '2.xs' must not open Q2 early."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("(2x4)3", 100, x1=160.0),
        _L("1.", 110, x1=40.0, x2=80.0),
        _L("2.xs", 120, x1=100.0, x2=200.0),  # junk, left-biased
        _L("A.", 200, x1=40.0, x2=80.0),
        _L("B.", 240, x1=40.0, x2=80.0),
        _L("C.", 280, x1=40.0, x2=80.0),
        _L("D.", 320, x1=40.0, x2=80.0),
        _L("(4x+y)^2-(4x-y)^2=", 400, x1=160.0),
        _L("2.", 410, x1=40.0, x2=80.0),
        _L("A.", 500, x1=40.0, x2=80.0),
        _L("B.", 540, x1=40.0, x2=80.0),
        _L("C.", 580, x1=40.0, x2=80.0),
        _L("D.", 620, x1=40.0, x2=80.0),
        _L("3.", 700, x1=40.0, x2=80.0),
        _L("A.", 740, x1=40.0, x2=80.0),
        _L("B.", 780, x1=40.0, x2=80.0),
        _L("C.", 820, x1=40.0, x2=80.0),
        _L("D.", 860, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [1, 2, 3]
    assert regions[0].bbox[3] < regions[1].bbox[1] + 5


def test_preamble_skips_figure_crumbs_aligns_stem():
    """Axis labels between Qn and Qn+1 must not pull next y1 upward."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("32.", 100, x1=40.0, x2=90.0),
        _L("A.", 200, x1=40.0, x2=80.0),
        _L("B.", 240, x1=40.0, x2=80.0),
        _L("C.", 280, x1=40.0, x2=80.0),
        _L("D.", 320, x1=40.0, x2=80.0),
        _L("log3x", 400, x1=100.0, x2=200.0),  # figure crumb
        _L("33.1+2=", 500, x1=40.0, x2=200.0),
        _L("A.", 560, x1=40.0, x2=80.0),
        _L("B.", 600, x1=40.0, x2=80.0),
        _L("C.", 640, x1=40.0, x2=80.0),
        _L("D.", 680, x1=40.0, x2=80.0),
    ]
    regions = detect_mcq_regions(lines, profile)
    assert [r.question_id for r in regions] == [32, 33]
    # Q33 should start near its stem, not at log3x
    assert regions[1].bbox[1] >= 450
    # no overlap
    assert regions[0].bbox[3] <= regions[1].bbox[1] + 1


def test_last_question_extends_toward_footer():
    """Page-final MCQ (e.g. Q36/Q39) must keep diagram below D."""
    profile = load_mcq_profile(default_math_cp_p2_path())
    lines = [
        _L("36.", 1400, x1=40.0, x2=90.0),
        _L("A.", 1600, x1=40.0, x2=80.0),
        _L("B.", 1700, x1=40.0, x2=80.0),
        _L("C.", 1800, x1=40.0, x2=80.0),
        _L("D.", 1900, x1=40.0, x2=80.0),
    ]
    # Override page height via OcrLine
    lines = [
        OcrLine(text=ln.text, bbox=ln.bbox, page_width=W, page_height=H)
        for ln in lines
    ]
    regions = detect_mcq_regions(lines, profile)
    assert len(regions) == 1
    assert regions[0].bbox[3] >= H - profile.footer_margin_px - 1
