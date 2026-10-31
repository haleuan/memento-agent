"""Schema for achievement records (awards, papers, projects, etc.)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class AchievementReference(BaseModel):
    """An external link or identifier supporting an achievement."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["doi", "github", "pdf", "website", "certificate_id", "arxiv"]
    url: StrictStr = Field(min_length=1)


class AchievementItem(BaseModel):
    """A verifiable achievement or credential with supporting evidence.

    This type covers awards, publications, projects, work experience, and
    certificates. Each achievement should correspond to something that can
    be documented (a certificate, paper, project artifact, etc.) or verified
    by a third party.

    The agent extracts structured data from source documents (certificates,
    transcripts, etc.). The user writes the 'description' field, which explains
    their specific contribution or role.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["award", "paper", "project", "internship", "certificate", "work"] = (
        Field(
            description=(
                "Type of achievement:\n"
                "- 'award': Competitions, honors, scholarships (e.g., '国家奖学金', 'ACM-ICPC Gold Medal')\n"
                "- 'paper': Publications in journals, conferences, or preprint servers\n"
                "- 'project': Substantial coursework, research projects, or open-source contributions\n"
                "- 'internship': Temporary work experience, typically for students\n"
                "- 'certificate': Professional certifications or completed courses (e.g., 'AWS Certified', 'Deep Learning Specialization')\n"
                "- 'work': Full-time employment or contract work"
            )
        )
    )

    title: StrictStr = Field(
        min_length=1,
        description=(
            "Full name of the achievement as it appears on the certificate or official record. "
            "Extract this exactly as written in the source document.\n\n"
            "Examples:\n"
            "- '全国大学生数学建模竞赛'\n"
            "- 'Deep Learning Specialization'\n"
            "- 'Backend Development Internship'\n"
            "- 'Attention Is All You Need' (for a paper)"
        ),
    )

    organization: StrictStr = Field(
        min_length=1,
        description=(
            "Issuing organization, employer, conference, or host institution.\n\n"
            "The meaning varies by kind:\n"
            "- award: Awarding body (e.g., 'Education Department', 'Chinese Computer Society')\n"
            "- paper: Journal or conference (e.g., 'NeurIPS 2024', 'Nature')\n"
            "- project: Commissioning organization or academic institution\n"
            "- internship/work: Company name (e.g., 'ByteDance', 'Google')\n"
            "- certificate: Issuing platform or authority (e.g., 'Coursera', 'AWS', '人力资源和社会保障部')"
        ),
    )

    level_raw: StrictStr | None = Field(
        default=None,
        description=(
            "Award level, rank, or grade exactly as stated in the original document. "
            "Only applicable to 'award' and 'certificate' kinds. Leave null for other kinds.\n\n"
            "DO NOT normalize or translate. Extract the exact text.\n\n"
            "Examples:\n"
            "- 'National First Prize'\n"
            "- 'provincial second prize'\n"
            "- 'gold medal'\n"
            "- 'distinction' (for certificates)\n"
        ),
    )

    certificate_number: StrictStr | None = Field(
        default=None,
        min_length=1,
        description=(
            "Certificate or credential number exactly as stated in the source document. "
            "Leave null when the source does not provide one."
        ),
    )

    description: StrictStr | None = Field(
        default=None,
        description=(
            "User-authored description of their contributions, responsibilities, or outcomes. "
            "This field is NOT extracted from documents—it is written by the user to explain "
            "their specific role and impact.\n\n"
            "Use this content when generating resumes or application materials.\n\n"
            "Example:\n"
            "'Led a team of 3 to develop a real-time object detection system using YOLOv8. "
            "Optimized the model to achieve 95% mAP on our custom dataset while maintaining "
            "30 FPS inference speed on edge devices. Deployed the system in a production "
            "environment serving 10K+ daily requests.'"
        ),
    )

    collaborators: list[StrictStr] | None = Field(
        default=None,
        description=(
            "Names of co-authors, team members, or collaborators.\n"
            "Null or empty list indicates solo work.\n\n"
            "Examples:\n"
            "- Paper co-authors: ['John Smith', 'Jane Doe']\n"
            "- Project team: ['Linus Torvalds(advisor)', 'Jensen Huang']"
        ),
    )

    references: list[AchievementReference] | None = Field(
        default=None,
        description=(
            "External links for verification or additional information. "
            "Each reference has exactly two fields:\n"
            "- 'type': one of 'doi', 'github', 'pdf', 'website', 'certificate_id', 'arxiv'\n"
            "- 'url': the actual link or identifier\n\n"
            "Examples:\n"
            "[{'type': 'doi', 'url': '10.1109/CVPR.2024.12345'},\n"
            " {'type': 'github', 'url': 'https://github.com/user/repo'},\n"
            " {'type': 'arxiv', 'url': 'https://arxiv.org/abs/2301.12345'}]"
        ),
    )

    tags: list[StrictStr] | None = Field(
        default=None,
        description=(
            "Free-form tags for categorization, search, and filtering. "
            "Use lowercase with hyphens for multi-word tags.\n\n"
            "Examples:\n"
            "- ['deep-learning', 'computer-vision', 'pytorch']\n"
            "- ['algorithm-competition', 'dynamic-programming']\n"
            "- ['backend', 'distributed-systems', 'golang']"
        ),
    )
