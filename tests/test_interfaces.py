# pylint: disable=no-self-use
from tensorwaves.interface import FitResult


class TestFitResult:
    def test_count_number_of_parameters(self, fit_result: FitResult):
        assert fit_result.count_number_of_parameters(real=False) == 3
        assert fit_result.count_number_of_parameters(real=True) == 4
