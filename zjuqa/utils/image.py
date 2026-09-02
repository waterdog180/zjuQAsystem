"""
image.py —— 图片编码与加载工具。

提供 PDF 页面图片的 base64 编码和多模态消息格式转换，
供 extraction 层调用，减少重复代码。

使用说明：
    from zjuqa.utils.image import encode_image, load_images_for_paper
    images = load_images_for_paper("Test_1", max_images=40)
"""

import base64
from pathlib import Path
from typing import List

from ..utils.logging import get_logger
from ..utils.path_utils import get_parsed_images, get_parsed_images_cleaned

logger = get_logger(__name__)


def encode_image(image_path: Path) -> str:
    """
    将图片文件编码为 base64 字符串。

    Args:
        image_path: 图片文件路径

    Returns:
        base64 编码字符串
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def load_images_for_paper(
    paper_name: str,
    max_images: int = 40,
) -> List[dict]:
    """
    加载某篇论文的所有页面图片，编码为多模态消息格式。

    优先从 images_cleaned/ 加载（image_cleaner 清洗后的图片，按文中顺序重编号，小图已删除）；
    若该目录不存在或为空，则回退到原始 images/ 目录。

    Args:
        paper_name: 论文名称
        max_images: 最大图片数量，超长论文截断避免 token 超限

    Returns:
        多模态消息中的图片内容列表，每项为：
        {"type": "image_url", "image_url": {"url": "data:image/...;base64,..."}}
    """
    # 优先使用清洗后的图片目录
    cleaned_dir = get_parsed_images_cleaned(paper_name)
    images_dir = get_parsed_images(paper_name)

    if cleaned_dir.exists() and any(cleaned_dir.iterdir()):
        images_dir = cleaned_dir
        source = "cleaned"
    else:
        source = "original"

    if not images_dir.exists():
        logger.warning(f"图片目录不存在 {images_dir}")
        return []

    image_files = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
    image_files = image_files[:max_images]

    image_contents = []
    for img_path in image_files:
        b64 = encode_image(img_path)
        ext = img_path.suffix.lstrip(".")
        mime = (
            f"image/{ext}"
            if ext in ("jpeg", "jpg", "png", "webp")
            else "image/jpeg"
        )
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })

    logger.debug(f"加载 {len(image_contents)} 张页面图片（来源: {source}）")
    return image_contents
