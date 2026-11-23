import pandas as pd
from pandas.api.types import is_dtype_equal, is_numeric_dtype

from relatorios_service.pipeline_schemas import (
    Cardinality, ColumnStep, DeduplicateStep, DuplicateKeep, JoinStep, JoinType,
    Operation, PipelineMode, PipelinePlan, PipelineStep,
)
from relatorios_service.services.file_reader import FileReader
from relatorios_service.services.pipeline_errors import PipelineExecutionError
from relatorios_service.services.pipeline_transformations import PipelineTransformations


class JoinExecutor:
    def __init__(self, max_rows: int, max_columns: int) -> None:
        self.max_rows = max_rows
        self.max_columns = max_columns

    def columns(self, left: list[str], right: list[str], step: JoinStep) -> list[str]:
        frame = pd.DataFrame(columns=left).merge(
            pd.DataFrame(columns=right), left_on=step.left_on,
            right_on=step.right_on, how=step.how.value,
            suffixes=("_left", "_right"),
        )
        columns = list(frame.columns)
        if len(columns) != len(set(columns)) or len(columns) > self.max_columns:
            raise PipelineExecutionError("O join gera colunas duplicadas ou excede o limite.")
        return columns

    def execute(self, left: pd.DataFrame, right: pd.DataFrame, step: JoinStep) -> pd.DataFrame:
        for left_key, right_key in zip(step.left_on, step.right_on):
            left_type = left[left_key].dtype
            right_type = right[right_key].dtype
            if not (is_dtype_equal(left_type, right_type) or (
                is_numeric_dtype(left_type) and is_numeric_dtype(right_type)
            )):
                raise PipelineExecutionError("Converta as chaves do join para tipos compatíveis.")

        left_valid = left[step.left_on].notna().all(axis=1)
        right_valid = right[step.right_on].notna().all(axis=1)
        valid_left = left.loc[left_valid]
        valid_right = right.loc[right_valid]
        self._validate_cardinality(valid_left, valid_right, step)
        estimated = self._estimate_rows(valid_left, valid_right, step)
        if step.how in {JoinType.LEFT, JoinType.OUTER}:
            estimated += int((~left_valid).sum())
        if step.how in {JoinType.RIGHT, JoinType.OUTER}:
            estimated += int((~right_valid).sum())
        if estimated > self.max_rows:
            raise PipelineExecutionError("O join excederia o limite de linhas do pipeline.")

        parts = [self._merge(valid_left, valid_right, step)]
        # Semântica SQL: chaves nulas nunca se relacionam entre si.
        if step.how in {JoinType.LEFT, JoinType.OUTER} and (~left_valid).any():
            parts.append(self._merge(left.loc[~left_valid], right.iloc[:0], step))
        if step.how in {JoinType.RIGHT, JoinType.OUTER} and (~right_valid).any():
            parts.append(self._merge(left.iloc[:0], right.loc[~right_valid], step))
        return pd.concat(parts, ignore_index=True)

    def _merge(self, left: pd.DataFrame, right: pd.DataFrame, step: JoinStep) -> pd.DataFrame:
        return left.merge(
            right, left_on=step.left_on, right_on=step.right_on,
            how=step.how.value, suffixes=("_left", "_right"), sort=False,
        )

    def _validate_cardinality(self, left: pd.DataFrame, right: pd.DataFrame, step: JoinStep) -> None:
        if step.cardinality in {Cardinality.ONE_TO_ONE, Cardinality.ONE_TO_MANY}:
            if left.duplicated(step.left_on).any():
                raise PipelineExecutionError("A chave esquerda não é única para a cardinalidade escolhida.")
        if step.cardinality in {Cardinality.ONE_TO_ONE, Cardinality.MANY_TO_ONE}:
            if right.duplicated(step.right_on).any():
                raise PipelineExecutionError("A chave direita não é única para a cardinalidade escolhida.")

    def _estimate_rows(self, left: pd.DataFrame, right: pd.DataFrame, step: JoinStep) -> int:
        keys = [f"key_{index}" for index in range(len(step.left_on))]
        left_counts = left[step.left_on].set_axis(keys, axis=1).groupby(
            keys, observed=True, sort=False,
        ).size().rename("left_count").reset_index()
        right_counts = right[step.right_on].set_axis(keys, axis=1).groupby(
            keys, observed=True, sort=False,
        ).size().rename("right_count").reset_index()
        counts = left_counts.merge(right_counts, on=keys, how=step.how.value)
        # Inteiros Python evitam overflow ao estimar produtos muitos-para-muitos.
        return sum(
            int(left_count) * int(right_count)
            for left_count, right_count in counts[["left_count", "right_count"]].fillna(1).itertuples(index=False, name=None)
        )


class PipelineExecutor:
    def __init__(self, max_rows: int = 100000, max_columns: int = 500) -> None:
        self.max_rows = max_rows
        self.max_columns = max_columns
        self.joins = JoinExecutor(max_rows, max_columns)
        self.transformations = PipelineTransformations(max_rows)
        self.operations = {
            Operation.NULL_MARKERS: self._null_markers,
            Operation.DROP_NULLS: self._drop_nulls,
            Operation.DEDUPLICATE: self._deduplicate,
            Operation.SELECT: self._select,
            **self.transformations.operations,
        }

    def validate_plan(
        self, plan: PipelinePlan, frames: dict[str, pd.DataFrame], mode: PipelineMode,
    ) -> None:
        columns = {name: list(frame.columns) for name, frame in frames.items()}
        lineage = {name: {name} for name in frames}
        for step in plan.steps:
            if step.id in columns:
                raise ValueError("Cada etapa precisa ter um identificador novo e único.")
            if isinstance(step, JoinStep):
                if mode == PipelineMode.SEPARATE:
                    raise ValueError("O modo separate não permite joins.")
                self._validate_columns(columns, step.left, step.left_on)
                self._validate_columns(columns, step.right, step.right_on)
                if lineage[step.left] & lineage[step.right]:
                    raise ValueError("O join não pode repetir a mesma origem nos dois lados.")
                try:
                    columns[step.id] = self.joins.columns(columns[step.left], columns[step.right], step)
                except (ValueError, pd.errors.MergeError) as error:
                    raise ValueError("O join produz um esquema de colunas inválido.") from error
                lineage[step.id] = lineage[step.left] | lineage[step.right]
            else:
                self._validate_columns(columns, step.input, [])
                if step.operation not in self.transformations.operations:
                    self._validate_columns(columns, step.input, step.columns)
                    columns[step.id] = columns[step.input]
                    if step.operation == Operation.SELECT:
                        columns[step.id] = step.columns
                else:
                    columns[step.id] = self.transformations.columns(step, columns[step.input])
                if len(columns[step.id]) > self.max_columns:
                    raise ValueError("A etapa excede o limite de colunas.")
                lineage[step.id] = lineage[step.input]

        if len(set(plan.outputs)) != len(plan.outputs) or any(output not in columns for output in plan.outputs):
            raise ValueError("As saídas devem ser referências existentes e únicas.")
        chart_references = [chart.reference for chart in plan.charts]
        if len(set(chart_references)) != len(chart_references):
            raise ValueError("Cada saída aceita um gráfico planejado.")
        for chart in plan.charts:
            if chart.reference not in plan.outputs:
                raise ValueError("O gráfico deve referenciar uma saída do plano.")
            self._validate_columns(columns, chart.reference, [chart.x, chart.y])
        output_lineages = [lineage[output] for output in plan.outputs]
        if mode == PipelineMode.JOINED:
            if len(output_lineages) != 1 or output_lineages[0] != set(frames):
                raise ValueError("O modo joined exige uma saída que relacione todas as origens.")
        elif (len(output_lineages) != len(frames)
              or any(len(origin) != 1 for origin in output_lineages)
              or set.union(*output_lineages) != set(frames)):
            raise ValueError("O modo separate exige uma saída por origem.")

    def execute(self, step: PipelineStep, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        try:
            if isinstance(step, JoinStep):
                result = self.joins.execute(frames[step.left], frames[step.right], step)
            else:
                result = self.operations[step.operation](frames[step.input].copy(), step)
            if len(result) > self.max_rows or len(result.columns) > self.max_columns:
                raise PipelineExecutionError("O resultado excede os limites do pipeline.")
            return result.reset_index(drop=True)
        except PipelineExecutionError:
            raise
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            # Exceções do pandas podem carregar o valor inválido; não propagá-las à API/LLM.
            raise PipelineExecutionError(
                "A etapa falhou. Revise tipos, formatos e parâmetros antes de tentar novamente.",
            ) from error

    def input_rows(self, step: PipelineStep, frames: dict[str, pd.DataFrame]) -> list[int]:
        if isinstance(step, JoinStep):
            return [len(frames[step.left]), len(frames[step.right])]
        return [len(frames[step.input])]

    def _validate_columns(self, schemas: dict[str, list[str]], reference: str, columns: list[str]) -> None:
        if reference not in schemas or not set(columns).issubset(schemas[reference]):
            raise ValueError("A etapa referencia uma entrada ou coluna inexistente.")

    def _null_markers(self, frame: pd.DataFrame, step: ColumnStep) -> pd.DataFrame:
        for column in step.columns:
            values = frame[column].astype("string").str.casefold()
            frame[column] = frame[column].mask(values.isin(FileReader.null_markers), pd.NA)
        return frame

    def _drop_nulls(self, frame: pd.DataFrame, step: ColumnStep) -> pd.DataFrame:
        return frame.dropna(subset=step.columns)

    def _deduplicate(self, frame: pd.DataFrame, step: DeduplicateStep) -> pd.DataFrame:
        keep = step.keep.value
        if step.keep == DuplicateKeep.NONE:
            keep = False
        return frame.drop_duplicates(subset=step.columns, keep=keep)

    def _select(self, frame: pd.DataFrame, step: ColumnStep) -> pd.DataFrame:
        return frame[step.columns]
