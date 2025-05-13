from openai import OpenAI


class SiliconFlowVLM:
    """
    硅基流动视觉语言模型(VLM)适配器
    文档：https://docs.siliconflow.cn/cn/userguide/capabilities/vision

    支持的模型:
    - Qwen系列: Qwen/Qwen2.5-VL-32B-Instruct, Qwen/Qwen2.5-VL-72B-Instruct, Qwen/Qwen2-VL-72B-Instruct等
    - DeepseekVL2系列: deepseek-ai/deepseek-vl2
    """

    def __init__(
        self,
        api_key: str,
        model: str = "Qwen/Qwen2.5-VL-32B-Instruct",
        endpoint: str = "https://api.siliconflow.cn/v1",
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        初始化VLM适配器

        Args:
            api_key: 硅基流动API密钥
            model: 使用的VLM模型，默认为Qwen/Qwen2.5-VL-32B-Instruct
            endpoint: API端点，默认为硅基流动的聊天完成接口
            timeout: 请求超时时间(秒)
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url=endpoint,
        )
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def request(
        self,
        prompt: str,
        image_base64: str,
        image_format: str,
    ) -> str | None:
        """
        让vlm根据图片和文本提示词生成描述
        """
        responese = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/{image_format};base64,{image_base64}"},
                        },
                        {"type": "text", "text": f"{prompt}"},
                    ],
                }
            ],
        )

        return responese.choices[0].message.content
