# app/modules/blog/adapters/router/blog_routes.py
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

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

router = APIRouter(prefix="/blog", tags=["blog"])


@router.get("/", response_model=BlogListPage)
async def list_blogs(
    use_case: ListBlogsUseCaseDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    return await use_case.execute(limit=limit, skip=skip)


@router.get("/{blog_id}", response_model=BlogReadDTO)
async def get_blog_by_id(blog_id: UUID, use_case: GetBlogByIdUseCaseDep):
    entity = await use_case.execute(blog_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return entity


@router.get("/slug/{slug}", response_model=BlogReadDTO)
async def get_blog_by_slug(slug: str, use_case: GetBlogBySlugUseCaseDep):
    entity = await use_case.execute(slug)
    if not entity:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return entity


@router.post("/", response_model=BlogReadDTO, status_code=status.HTTP_201_CREATED)
async def create_blog(cmd: BlogCreateCmd, use_case: CreateBlogUseCaseDep):
    try:
        return await use_case.execute(cmd)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/", response_model=BlogReadDTO)
async def update_blog(cmd: BlogUpdateCmd, use_case: UpdateBlogUseCaseDep):
    try:
        entity = await use_case.execute(cmd)
        if not entity:
            raise HTTPException(status_code=404, detail="Blog post not found.")
        return entity
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{blog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blog(blog_id: UUID, use_case: DeleteBlogUseCaseDep):
    deleted = await use_case.execute(blog_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Blog post not found.")
