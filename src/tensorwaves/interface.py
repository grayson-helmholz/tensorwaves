"""Defines top-level interface of tensorwaves."""

from abc import ABC, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Mapping,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import attr
import numpy as np
from attr.validators import instance_of, optional

if TYPE_CHECKING:
    from IPython.lib.pretty import PrettyPrinter


InputType = TypeVar("InputType")
"""The argument type of a :meth:`.Function.__call__`."""
OutputType = TypeVar("OutputType")
"""The return type of a :meth:`.Function.__call__`."""


class Function(ABC, Generic[InputType, OutputType]):
    """Generic representation of a mathematical function.

    Representation of a `mathematical function
    <https://en.wikipedia.org/wiki/Function_(mathematics)>`_ that computes
    `.OutputType` values (co-domain) for a given set of `.InputType` values
    (domain). Examples of `Function` are `ParametrizedFunction`, `Estimator`
    and `DataTransformer`.
    """

    @abstractmethod
    def __call__(self, data: InputType) -> OutputType:
        ...


DataSample = Dict[str, np.ndarray]
"""Mapping of variable names to a sequence of data points, used by `Function`."""
ParameterValue = Union[complex, float]
"""Allowed types for parameter values."""


class ParametrizedFunction(Function[DataSample, np.ndarray]):
    """Interface of a callable function.

    A `ParametrizedFunction` identifies certain variables in a mathematical
    expression as **parameters**. Remaining variables are considered **domain
    variables**. Domain variables are the argument of the evaluation (see
    :func:`~Function.__call__`), while the parameters are controlled via
    :attr:`parameters` (getter) and :meth:`update_parameters` (setter). This
    mechanism is especially important for an `Estimator`.
    """

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, ParameterValue]:
        """Get `dict` of parameters."""

    @abstractmethod
    def update_parameters(
        self, new_parameters: Mapping[str, ParameterValue]
    ) -> None:
        """Update the collection of parameters."""


class DataTransformer(Function[DataSample, DataSample]):
    """Transform one `.DataSample` into another `.DataSample`.

    This changes the keys and values of the input `.DataSample` to a
    specific output `.DataSample` structure.
    """


class Estimator(Function[Mapping[str, ParameterValue], float]):
    """Estimator for discrepancy model and data.

    See the :mod:`.estimator` module for different implementations of this
    interface.
    """

    def __call__(self, parameters: Mapping[str, ParameterValue]) -> float:
        """Compute estimator value for this combination of parameter values."""

    @abstractmethod
    def gradient(
        self, parameters: Mapping[str, ParameterValue]
    ) -> Dict[str, ParameterValue]:
        """Calculate gradient for given parameter mapping."""


_PARAMETER_DICT_VALIDATOR = attr.validators.deep_mapping(
    key_validator=instance_of(str),
    mapping_validator=instance_of(dict),
    value_validator=instance_of(ParameterValue.__args__),  # type: ignore[attr-defined]
)


@attr.frozen
class FitResult:  # pylint: disable=too-many-instance-attributes
    minimum_valid: bool = attr.ib(validator=instance_of(bool))
    execution_time: float = attr.ib(validator=instance_of(float))
    function_calls: int = attr.ib(validator=instance_of(int))
    estimator_value: float = attr.ib(validator=instance_of(float))
    parameter_values: Dict[str, ParameterValue] = attr.ib(
        default=None, validator=_PARAMETER_DICT_VALIDATOR
    )
    parameter_errors: Optional[Dict[str, ParameterValue]] = attr.ib(
        default=None, validator=optional(_PARAMETER_DICT_VALIDATOR)
    )
    iterations: Optional[int] = attr.ib(
        default=None, validator=optional(instance_of(int))
    )
    specifics: Optional[Any] = attr.ib(default=None)
    """Any additional info provided by the specific optimizer.

    An instance returned by one of the implemented optimizers under the
    :mod:`.optimizer` module. Currently one of:

    - `iminuit.Minuit`
    - `scipy.optimize.OptimizeResult`

    This way, you can for instance get the `~iminuit.Minuit.covariance` matrix.
    See also :ref:`amplitude-analysis:Covariance matrix`.
    """

    @parameter_errors.validator  # pyright: reportOptionalMemberAccess=false
    def _check_parameter_errors(
        self, _: attr.Attribute, value: Optional[Dict[str, ParameterValue]]
    ) -> None:
        if value is None:
            return
        for par_name in value:
            if par_name not in self.parameter_values:
                raise ValueError(
                    "No parameter value exists for parameter error"
                    f' "{par_name}"'
                )

    def _repr_pretty_(self, p: "PrettyPrinter", cycle: bool) -> None:
        class_name = type(self).__name__
        if cycle:
            p.text(f"{class_name}(...)")
        else:
            with p.group(indent=1, open=f"{class_name}("):
                for field in attr.fields(type(self)):
                    if field.name in {"specifics"}:
                        continue
                    value = getattr(self, field.name)
                    if value != field.default:
                        p.breakable()
                        p.text(f"{field.name}=")
                        if isinstance(value, dict):
                            with p.group(indent=1, open="{"):
                                for key, val in value.items():
                                    p.breakable()
                                    p.pretty(key)
                                    p.text(": ")
                                    p.pretty(val)
                                    p.text(",")
                            p.breakable()
                            p.text("}")
                        else:
                            p.pretty(value)
                        p.text(",")
            p.breakable()
            p.text(")")

    def count_number_of_parameters(self, complex_twice: bool = False) -> int:
        """Compute the number of free parameters in a `.FitResult`.

        Args:
            complex_twice (bool): Count complex-valued parameters twice.
        """
        n_parameters = len(self.parameter_values)
        if complex_twice:
            complex_values = filter(
                lambda v: isinstance(v, complex),
                self.parameter_values.values(),
            )
            n_parameters += len(list(complex_values))
        return n_parameters


class Optimizer(ABC):
    """Optimize a fit model to a data set.

    See the :mod:`.optimizer` module for different implementations of this
    interface.
    """

    @abstractmethod
    def optimize(
        self,
        estimator: Estimator,
        initial_parameters: Mapping[str, ParameterValue],
    ) -> FitResult:
        """Execute optimization."""


class RealNumberGenerator(ABC):
    """Abstract class for generating real numbers within a certain range.

    Implementations can be found in the `tensorwaves.data` module.
    """

    @abstractmethod
    def __call__(
        self, size: int, min_value: float = 0.0, max_value: float = 1.0
    ) -> np.ndarray:
        """Generate random floats in the range [min_value, max_value)."""

    @property  # type: ignore[misc]
    @abstractmethod
    def seed(self) -> Optional[float]:
        """Get random seed. `None` if you want indeterministic behavior."""

    @seed.setter  # type: ignore[misc]
    @abstractmethod
    def seed(self, value: Optional[float]) -> None:
        """Set random seed. Use `None` for indeterministic behavior."""


class DataGenerator(ABC):
    """Abstract class for generating a `.DataSample`."""

    @abstractmethod
    def generate(self, size: int, rng: RealNumberGenerator) -> DataSample:
        ...


class WeightedDataGenerator(ABC):
    """Abstract class for generating a `.DataSample` with weights."""

    @abstractmethod
    def generate(
        self, size: int, rng: RealNumberGenerator
    ) -> Tuple[DataSample, np.ndarray]:
        r"""Generate `.DataSample` with weights.

        Returns:
            A `tuple` of a `.DataSample` with an array of weights.
        """
