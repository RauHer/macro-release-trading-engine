from macro_engine.models import MacroRelease
from macro_engine.release_assessment import AssessmentType, assess_release


def test_forecast_relative_cpi_assessment():
    assessment = assess_release(MacroRelease(country_code="US", event_code="CPI", actual=3.4, forecast=3.2, previous=3.1))

    assert assessment.assessment_type == AssessmentType.FORECAST_RELATIVE
    assert assessment.absolute_deviation == 0.19999999999999973
    assert assessment.mathematical_comparison == "Greater than forecast"
    assert assessment.trader_interpretation == "Hotter than forecast"


def test_previous_relative_pmi_assessment():
    assessment = assess_release(MacroRelease(country_code="NZ", event_code="PMI_MFG", actual=47.5, forecast=None, previous=48.3))

    assert assessment.assessment_type == AssessmentType.THRESHOLD_RELATIVE
    assert round(assessment.previous_change, 1) == -0.8
    assert assessment.mathematical_comparison == "Lesser than previous"
    assert assessment.trader_interpretation == "Weaker than previous"
    assert assessment.threshold_context == "Below 50, indicating contractionary survey conditions."
