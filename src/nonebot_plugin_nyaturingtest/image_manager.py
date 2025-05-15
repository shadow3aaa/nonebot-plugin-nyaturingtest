import base64
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path

from nonebot import logger
import numpy as np
from PIL import Image

from nonebot_plugin_nyaturingtest.vlm import SiliconFlowVLM

from .config import plugin_config

IMAGE_CACHE_DIR = Path("image_cache")


@dataclass
class ImageWithDescription:
    """
    图片和描述
    """

    description: str
    """
    图像内容简述
    """
    emotion: str
    """
    图像情感关键词
    """
    is_sticker: bool = False
    """
    是否是贴图
    """

    def to_json(self) -> str:
        """
        将对象转换为JSON字符串
        """
        return json.dumps(self.__dict__, ensure_ascii=False)

    @staticmethod
    def from_json(json_str: str) -> "ImageWithDescription":
        """
        从JSON字符串转换为对象，错误时抛出
        """
        image_with_desc = ImageWithDescription("", "", False)
        data = json.loads(json_str)
        # 检查数据完整性
        if not all(key in data for key in ["description", "emotion", "is_sticker"]):
            raise ValueError("缺少必要的字段")
        image_with_desc.description = data["description"]
        image_with_desc.emotion = data["emotion"]
        image_with_desc.is_sticker = data["is_sticker"]
        return image_with_desc


class ImageManager:
    """
    图片管理
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._vlm = SiliconFlowVLM(
                api_key=plugin_config.nyaturingtest_siliconflow_api_key,
                model="Pro/Qwen/Qwen2.5-VL-7B-Instruct",
            )
            IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._initialized = True

    def get_image_description(self, image_base64: str, is_sticker: bool) -> ImageWithDescription | None:
        """
        获取图片描述
        """
        image_bytes = base64.b64decode(image_base64)
        # 计算图片的SHA256哈希值
        image_hash = _calculate_image_hash(image_bytes)
        # 检查缓存
        cache = IMAGE_CACHE_DIR.joinpath(f"{image_hash}.json")
        if cache.exists():
            with open(cache, encoding="utf-8") as f:
                image_with_desc_raw = f.read()
                try:
                    image_with_desc = ImageWithDescription.from_json(image_with_desc_raw)
                    if image_with_desc.is_sticker != is_sticker:
                        image_with_desc.is_sticker = is_sticker
                        # 修改缓存文件
                        with open(cache, "w", encoding="utf-8") as f:
                            f.write(image_with_desc.to_json())
                    return image_with_desc
                except ValueError as e:
                    logger.error(f"缓存文件({cache})格式错误，重新生成")
                    logger.error(e)
                    cache.unlink()  # 删除缓存文件

        # 获取图片描述
        # 获取图片类型
        image_format = Image.open(io.BytesIO(image_bytes)).format
        if not image_format:
            logger.error("无法识别的图片格式")
            return None

        # 调用VLM获取描述
        if image_format == "gif" or image_format == "GIF":
            gif_transfromed = _transform_gif(image_base64)
            if not gif_transfromed:
                logger.error("GIF转换失败")
                return None
            prompt = """这是一个动态图，每一张图代表了动态图的某一帧，黑色背景代表透明。"请用中文描述这张图片的内容。如
            果有文字，请把文字都描述出来。并尝试猜测这个图片的含义。最多100个字"""
            description = self._vlm.request(
                prompt=prompt,
                image_base64=gif_transfromed,
                image_format="jpeg",
            )
            # 分析表达的情感
            prompt = """这是一个动态图，每一张图代表了动态图的某一帧，黑色背景代表透明。请分析这个表情包表达的情感，
            用中文给出'情感，类型，含义'的三元式描述，要求每个描述都是一个简单的词语"""
            description_emotion = self._vlm.request(
                prompt=prompt,
                image_base64=gif_transfromed,
                image_format="jpeg",
            )
        else:
            prompt = "请用中文描述这张图片的内容。如果有文字，请把文字都描述出来。并尝试猜测这个图片的含义。最多100个字"
            description = self._vlm.request(
                prompt=prompt,
                image_base64=image_base64,
                image_format=image_format,
            )
            # 分析表达的情感
            prompt = """请分析这个表情包表达的情感，用中文给出'情感，类型，含义'的三元式描述，要求每个描述都是一个简单的
            词语"""
            description_emotion = self._vlm.request(
                prompt=prompt,
                image_base64=image_base64,
                image_format="jpeg",
            )

        if not description or not description_emotion:
            logger.error("VLM请求失败")
            return None

        result = ImageWithDescription(
            description=description,
            emotion=description_emotion,
            is_sticker=is_sticker,
        )

        # 缓存结果
        with open(cache, "w", encoding="utf-8") as f:
            f.write(result.to_json())

        return result


def _transform_gif(gif_base64: str, similarity_threshold: float = 1000.0, max_frames: int = 15) -> str | None:
    """将GIF转换为水平拼接的静态图像, 跳过相似的帧

    来自 MAIBOT(https://github.com/MaiM-with-u/MaiBot)

    Args:
        gif_base64: GIF的base64编码字符串
        similarity_threshold: 判定帧相似的阈值 (MSE)，越小表示要求差异越大才算不同帧，默认1000.0
        max_frames: 最大抽取的帧数，默认15

    Returns:
        Optional[str]: 拼接后的JPG图像的base64编码字符串, 或者在失败时返回None
    """
    try:
        # 解码base64
        gif_data = base64.b64decode(gif_base64)
        gif = Image.open(io.BytesIO(gif_data))

        # 收集所有帧
        all_frames = []
        try:
            while True:
                gif.seek(len(all_frames))
                # 确保是RGB格式方便比较
                frame = gif.convert("RGB")
                all_frames.append(frame.copy())
        except EOFError:
            pass  # 读完啦

        if not all_frames:
            logger.warning("GIF中没有找到任何帧")
            return None  # 空的GIF直接返回None

        # --- 新的帧选择逻辑 ---
        selected_frames = []
        last_selected_frame_np = None

        for i, current_frame in enumerate(all_frames):
            current_frame_np = np.array(current_frame)

            # 第一帧总是要选的
            if i == 0:
                selected_frames.append(current_frame)
                last_selected_frame_np = current_frame_np
                continue

            # 计算和上一张选中帧的差异（均方误差 MSE）
            if last_selected_frame_np is not None:
                mse = np.mean((current_frame_np - last_selected_frame_np) ** 2)
                # logger.trace(f"帧 {i} 与上一选中帧的 MSE: {mse}") # 可以取消注释来看差异值

                # 如果差异够大，就选它！
                if mse > similarity_threshold:
                    selected_frames.append(current_frame)
                    last_selected_frame_np = current_frame_np
                    # 检查是不是选够了
                    if len(selected_frames) >= max_frames:
                        # logger.debug(f"已选够 {max_frames} 帧，停止选择。")
                        break
            # 如果差异不大就跳过这一帧啦

        # --- 帧选择逻辑结束 ---

        # 如果选择后连一帧都没有（比如GIF只有一帧且后续处理失败？）或者原始GIF就没帧，也返回None
        if not selected_frames:
            logger.warning("处理后没有选中任何帧")
            return None

        # logger.debug(f"总帧数: {len(all_frames)}, 选中帧数: {len(selected_frames)}")

        # 获取选中的第一帧的尺寸（假设所有帧尺寸一致）
        frame_width, frame_height = selected_frames[0].size

        # 计算目标尺寸，保持宽高比
        target_height = 200  # 固定高度
        # 防止除以零
        if frame_height == 0:
            logger.error("帧高度为0，无法计算缩放尺寸")
            return None
        target_width = int((target_height / frame_height) * frame_width)
        # 宽度也不能是0
        if target_width == 0:
            logger.warning(f"计算出的目标宽度为0 (原始尺寸 {frame_width}x{frame_height})，调整为1")
            target_width = 1

        # 调整所有选中帧的大小
        resized_frames = [
            frame.resize((target_width, target_height), Image.Resampling.LANCZOS) for frame in selected_frames
        ]

        # 创建拼接图像
        total_width = target_width * len(resized_frames)
        # 防止总宽度为0
        if total_width == 0 and len(resized_frames) > 0:
            logger.warning("计算出的总宽度为0，但有选中帧，可能目标宽度太小")
            # 至少给点宽度吧
            total_width = len(resized_frames)
        elif total_width == 0:
            logger.error("计算出的总宽度为0且无选中帧")
            return None

        combined_image = Image.new("RGB", (total_width, target_height))

        # 水平拼接图像
        for idx, frame in enumerate(resized_frames):
            combined_image.paste(frame, (idx * target_width, 0))

        # 转换为base64
        buffer = io.BytesIO()
        combined_image.save(buffer, format="JPEG", quality=85)  # 保存为JPEG
        result_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return result_base64

    except MemoryError:
        logger.error("GIF转换失败: 内存不足，可能是GIF太大或帧数太多")
        return None  # 内存不够啦
    except Exception as e:
        logger.error(f"GIF转换失败: {e}", exc_info=True)  # 记录详细错误信息
        return None  # 其他错误也返回None


def _calculate_image_hash(image: bytes) -> str:
    """
    计算图片的SHA256哈希值
    """
    sha256_hash = hashlib.md5(image).hexdigest()
    return sha256_hash


image_manager = ImageManager()
