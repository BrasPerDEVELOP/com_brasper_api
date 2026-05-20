# app/modules/blog/adapters/router
from app.modules.blog.adapters.router.blog_routes import router as blog_routes

router = blog_routes

__all__ = ["router"]
