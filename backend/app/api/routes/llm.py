from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import RequestContext, require_platform_operator, require_roles
from app.core.config import Settings, get_settings
from app.db.enums import Role
from app.db.models import LlmConfiguration, LlmPreset
from app.schemas.ai import ProposalRequest, ProposalResponse
from app.schemas.llm import (
    LlmConfigurationRequest,
    LlmConfigurationResponse,
    PresetCreateRequest,
    PresetResponse,
    PresetUpdateRequest,
)
from app.services.llm import (
    create_configuration,
    create_preset,
    generate_proposal,
    test_configuration,
)

router = APIRouter(prefix="/llm", tags=["llm"])
admin = require_roles(Role.ORGANIZATION_ADMIN)


@router.get("/presets", response_model=list[PresetResponse])
def list_presets(context: RequestContext = Depends(admin)) -> list[PresetResponse]:  # noqa: B008
    presets = context.db.scalars(
        select(LlmPreset)
        .where(LlmPreset.is_active.is_(True))
        .order_by(LlmPreset.provider, LlmPreset.name)
    ).all()
    return [PresetResponse.model_validate(preset) for preset in presets]


@router.get("/operator/presets", response_model=list[PresetResponse])
def list_operator_presets(
    context: RequestContext = Depends(require_platform_operator),  # noqa: B008
) -> list[PresetResponse]:
    presets = context.db.scalars(
        select(LlmPreset).order_by(LlmPreset.provider, LlmPreset.name)
    ).all()
    return [PresetResponse.model_validate(preset) for preset in presets]


@router.post("/presets", response_model=PresetResponse, status_code=201)
def add_preset(
    payload: PresetCreateRequest, context: RequestContext = Depends(require_platform_operator)
) -> PresetResponse:  # noqa: B008
    return PresetResponse.model_validate(create_preset(context.db, payload))


@router.post("/presets/{preset_id}/deactivate", response_model=PresetResponse)
def deactivate_preset(
    preset_id: UUID, context: RequestContext = Depends(require_platform_operator)
) -> PresetResponse:  # noqa: B008
    preset = context.db.get(LlmPreset, preset_id)
    if not preset:
        from app.core.errors import NotFoundError

        raise NotFoundError("Preset não encontrado.")
    preset.is_active = False
    context.db.commit()
    return PresetResponse.model_validate(preset)


@router.patch("/presets/{preset_id}", response_model=PresetResponse)
def update_preset(
    preset_id: UUID,
    payload: PresetUpdateRequest,
    context: RequestContext = Depends(require_platform_operator),  # noqa: B008
) -> PresetResponse:
    preset = context.db.get(LlmPreset, preset_id)
    if not preset:
        from app.core.errors import NotFoundError

        raise NotFoundError("Preset não encontrado.")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(preset, key, value)
    context.db.commit()
    context.db.refresh(preset)
    return PresetResponse.model_validate(preset)


@router.get("/configurations", response_model=list[LlmConfigurationResponse])
def list_configurations(context: RequestContext = Depends(admin)) -> list[LlmConfigurationResponse]:  # noqa: B008
    configurations = context.db.scalars(
        select(LlmConfiguration)
        .where(LlmConfiguration.organization_id == context.organization.id)
        .order_by(LlmConfiguration.name)
    ).all()
    return [
        LlmConfigurationResponse.model_validate(configuration) for configuration in configurations
    ]


@router.post("/configurations", response_model=LlmConfigurationResponse, status_code=201)
def add_configuration(
    payload: LlmConfigurationRequest,
    context: RequestContext = Depends(admin),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> LlmConfigurationResponse:
    configuration = create_configuration(
        context.db, settings, context.organization.id, context.user.id, payload
    )
    return LlmConfigurationResponse.model_validate(configuration)


@router.post("/configurations/{configuration_id}/test")
def test_llm_configuration(
    configuration_id: UUID,
    context: RequestContext = Depends(admin),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, object]:
    return test_configuration(
        context.db, settings, configuration_id, context.organization.id, context.user.id
    )


@router.post("/proposals", response_model=ProposalResponse)
def proposal(
    payload: ProposalRequest,
    context: RequestContext = Depends(require_roles(Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR)),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ProposalResponse:
    result = generate_proposal(
        context.db,
        settings,
        payload.configuration_id,
        context.organization.id,
        context.user.id,
        payload.objective,
        payload.catalog_context,
    )
    return ProposalResponse.model_validate(result)
