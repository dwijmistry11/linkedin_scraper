from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PostEngagementUser(BaseModel):
    """A user who reacted to or reposted a LinkedIn post."""
    name: str
    headline: Optional[str] = None
    profile_url: Optional[str] = None
    engagement_type: str  # "reaction" or "repost"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ExtractUsersResult(BaseModel):
    """Result of extracting engaged users from a company's posts."""
    company_url: str
    posts_scraped: int
    users: List["PostEngagementUser"] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()

    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)


class Post(BaseModel):
    linkedin_url: Optional[str] = None
    urn: Optional[str] = None
    text: Optional[str] = None
    posted_date: Optional[str] = None
    reactions_count: Optional[int] = None
    comments_count: Optional[int] = None
    reposts_count: Optional[int] = None
    image_urls: List[str] = Field(default_factory=list)
    video_url: Optional[str] = None
    article_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
    
    def to_json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)
    
    def __repr__(self) -> str:
        text_preview = self.text[:80] + "..." if self.text and len(self.text) > 80 else self.text
        return (
            f"<Post\n"
            f"  Text: {text_preview}\n"
            f"  Posted: {self.posted_date}\n"
            f"  Reactions: {self.reactions_count}\n"
            f"  Comments: {self.comments_count}>"
        )
