# app/modules/blog/adapters/router/blog_routes.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.blog.application.schemas import (
    BlogCreateCmd,
    BlogUpdateCmd,
    BlogReadDTO,
    BlogListPage,
)
from app.modules.blog.adapters.dependencies import (
    GetBlogByIdUseCaseDep,
    GetBlogBySlugUseCaseDep,
    ListBlogsUseCaseDep,
    CreateBlogUseCaseDep,
    UpdateBlogUseCaseDep,
    DeleteBlogUseCaseDep,
)

from app.core.routing import LegacyAliasRouter
from app.modules.auth.infrastructure.dependencies import has_permission, require_permission

router = LegacyAliasRouter(prefix="/blog", tags=["blog"])


@router.get("", response_model=BlogListPage)
async def list_blogs(
    use_case: ListBlogsUseCaseDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, min_length=1),
    category: str | None = Query(None, min_length=1),
    enable: bool | None = Query(None),
    can_view_drafts: bool = Depends(has_permission("blog.view")),
):
    if not can_view_drafts:
        enable = True
    return await use_case.execute(
        limit=limit,
        skip=skip,
        search=search,
        category=category,
        enable=enable,
    )


@router.get("/{blog_id}", response_model=BlogReadDTO)
async def get_blog_by_id(
    blog_id: UUID,
    use_case: GetBlogByIdUseCaseDep,
    _permissions=Depends(require_permission("blog.view")),
):
    entity = await use_case.execute(blog_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return entity


@router.get("/slug/{slug}", response_model=BlogReadDTO)
async def get_blog_by_slug(
    slug: str,
    use_case: GetBlogBySlugUseCaseDep,
    can_view_drafts: bool = Depends(has_permission("blog.view")),
):
    entity = await use_case.execute(slug)
    if not entity or (not entity.enable and not can_view_drafts):
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return entity


from app.modules.audit.infrastructure.stage_mutation_audit import stage_mutation_audit


@router.post("", response_model=BlogReadDTO, status_code=status.HTTP_201_CREATED)
async def create_blog(
    cmd: BlogCreateCmd,
    use_case: CreateBlogUseCaseDep,
    _permissions=Depends(require_permission("blog.create")),
    audit_event=Depends(stage_mutation_audit("blog.create", "blog")),
):
    try:
        created = await use_case.execute(cmd)
        if audit_event and created:
            audit_event.entity_id = str(created.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        return created
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("", response_model=BlogReadDTO)
async def update_blog(
    cmd: BlogUpdateCmd,
    use_case: UpdateBlogUseCaseDep,
    get_use_case: GetBlogByIdUseCaseDep,
    _permissions=Depends(require_permission("blog.update")),
    audit_event=Depends(stage_mutation_audit("blog.update", "blog")),
):
    try:
        previous = await get_use_case.execute(cmd.id)
        if audit_event and previous:
            audit_event.old_values = previous.model_dump(mode="json")
        entity = await use_case.execute(cmd)
        if audit_event and entity:
            audit_event.entity_id = str(entity.id)
            audit_event.new_values = cmd.model_dump(mode="json")
        if not entity:
            raise HTTPException(status_code=404, detail="Blog post not found.")
        return entity
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog(
    blog_id: UUID,
    use_case: DeleteBlogUseCaseDep,
    get_use_case: GetBlogByIdUseCaseDep,
    _permissions=Depends(require_permission("blog.delete")),
    audit_event=Depends(stage_mutation_audit("blog.delete", "blog")),
):
    previous = await get_use_case.execute(blog_id)
    if audit_event:
        audit_event.entity_id = str(blog_id)
        audit_event.old_values = previous.model_dump(mode="json") if previous else None
    deleted = await use_case.execute(blog_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Blog post not found.")
