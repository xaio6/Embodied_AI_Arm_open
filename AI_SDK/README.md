# AI_SDK 开发者文档

AI_SDK 提供一个统一、简洁的 Python 接口，聚合多家 AI 能力：
- LLM 大语言模型（聊天/流式/异步/上下文会话）
- ASR 语音识别（文件/麦克风/实时流/关键词唤醒）
- TTS 语音合成（文件/扬声器/流式边听边说）
- 多模态（图像/视频理解，多图像分析）
- 智能对话（LLM + TTS 一体化）

面向“应用层开发者”：你只需调用 SDK 方法，不需要了解底层供应商的差异和协议细节。

---

## 安装与环境

- 推荐直接使用项目根目录的依赖：
  ```bash
  pip install -r requirements.txt
  ```
- Windows 安装 `pyaudio` 可能需要：
  ```bash
  pip install pipwin && pipwin install pyaudio
  ```

## 配置（强烈建议用环境变量注入密钥）

默认读取 `config/aisdk_config.yaml`，也可传入 `config_dict`。建议将密钥以环境变量形式配置，例如：

```yaml
providers:
  alibaba:
    api_key: ${ALI_API_KEY}
    default_params:
      max_tokens: 2000
      temperature: 0.7
      top_p: 0.8
    enabled: true
  deepseek:
    api_key: ${DEEPSEEK_API_KEY}
    default_params:
      max_tokens: 2000
      temperature: 0.7
      top_p: 1.0
    enabled: true
```

- 支持覆盖的常见配置：
  - `request`: `timeout`, `max_retries`, `retry_delay`
  - `logging`: `level`, `file`, `max_size`, `backup_count`
  - `session`: `default_max_history`, `max_sessions`
  - `providers.*.default_params`: 每家默认模型参数（`temperature`, `top_p`, `max_tokens` 等）

---

## 快速开始

```python
from AI_SDK import AISDK

sdk = AISDK()  # 默认读取 config/aisdk_config.yaml

# 1) 基础聊天（同步）
resp = sdk.chat(provider="alibaba", model="qwen-turbo", prompt="你好")
print(resp)

# 2) 流式聊天（同步流）
for chunk in sdk.chat("alibaba", "qwen-turbo", "讲个笑话", stream=True):
    print(chunk, end="")

# 3) 上下文对话（自动管理历史）
sdk.chat("alibaba", "qwen-turbo", "我叫张三", use_context=True)
name = sdk.chat("alibaba", "qwen-turbo", "我叫什么？", use_context=True)

# 4) 异步调用（需在异步环境中）
# response = await sdk.chat("alibaba", "qwen-turbo", "你好", async_mode=True)
```

---

## ASR 语音识别

```python
# 文件识别
r = sdk.asr(provider="alibaba", mode="file", audio_file="audio.wav")

# 麦克风识别（duration: 秒）
r = sdk.asr("alibaba", "microphone", duration=5)

# 实时流识别（传入音频流/生成器）
for out in sdk.asr("alibaba", "stream", audio_stream=my_stream()):
    print(out)

# 关键词检测（流式唤醒）
for out in sdk.asr("alibaba", "keyword", keywords=["你好", "小助手"]):
    if out.get("success"):
        print("唤醒词：", out.get("keyword_detected"))
```

常用参数：`audio_file`、`duration`、`audio_stream`、`keywords`、`async_mode` 等。

---

## TTS 语音合成

```python
# 文本转语音 → 保存到文件
r = sdk.tts(provider="alibaba", mode="file", text="你好世界", output_file="out.mp3")

# 文本转语音 → 扬声器播放
r = sdk.tts("alibaba", "speaker", "欢迎使用AI_SDK")

# 流式合成（配合LLM流式输出或自定义生成器）
def text_gen():
    yield "今天天气"
    yield "不错"
for r in sdk.tts("alibaba", "stream", text_gen()):
    print("chunk done")
```

常用参数：`voice`, `sample_rate`, `format`, `speaker`, `prosody` 等（依具体提供商/模型）。

---

## 多模态（图像/视频）

```python
# 图像理解
r = sdk.multimodal(provider="alibaba", mode="image", prompt="描述这张图", image_path="image.jpg")

# 视频分析
r = sdk.multimodal("alibaba", "video", "这个视频讲了什么", video_path="video.mp4")

# 多图像分析
r = sdk.multimodal("alibaba", "multiple_images", "比较这些图片", image_paths=["a.jpg", "b.jpg"])  # 通过kwargs传入
```

常用参数：`model`（如 `qwen-vl-max-latest`）、`temperature`、`max_tokens`、`fps`（视频抽帧）等。

---

## 智能对话（LLM + TTS 一体化）

```python
# 直接问答并语音播放
o = sdk.smart_chat(
    prompt="请用两句话介绍一下你自己",
    llm_provider="alibaba", llm_model="qwen-turbo",
    tts_provider="alibaba", tts_model="sambert-zhichu-v1",
    tts_mode="speaker",  # 或 "file"/"stream"
    use_context=False,
)
print(o)
```

进阶：`smart_multimodal_chat`（图像/视频 + 文本）、`smart_voice_chat`（语音端到端）、`smart_multimodal_voice_chat`。

---

## 会话与上下文

```python
# 使用默认全局历史
sdk.chat("alibaba", "qwen-turbo", "记住我叫王五", use_context=True)

# 自定义会话ID
a_id = "user_A"
sdk.create_session(session_id=a_id, max_history=30)
sdk.chat("alibaba", "qwen-turbo", "我喜欢足球", use_context=True, session_id=a_id)

# 历史管理
hist = sdk.get_conversation_history(session_id=a_id)
sdk.set_conversation_history(hist[-10:], session_id=a_id)
sdk.clear_conversation_history(session_id=a_id)

# 会话管理
sdk.list_sessions()
sdk.delete_session(a_id)
```

---

## 切换提供商与模型

```python
# 查看可用提供商
deps = sdk.get_available_providers()

# 查看提供商可用模型
models = sdk.get_provider_models("alibaba")

# 在同一套API下切换到DeepSeek
o = sdk.chat(provider="deepseek", model="deepseek-chat", prompt="Explain RAG in 1 sentence")
```

你也可以在 `config/aisdk_config.yaml` 中启用/禁用提供商或修改 `default_params`。

---

## 异步与流式

- 任意接口均可设置 `async_mode=True` 获得 `await` 版本
- LLM 与 TTS 支持 `stream=True` 或对应的流式生成器

```python
# 异步流式
# async for chunk in sdk.chat("alibaba", "qwen-turbo", "你好", stream=True, async_mode=True):
#     print(chunk)
```

---

## 错误处理与日志

```python
from AI_SDK.utils.exceptions import AISDKException

try:
    sdk.chat("alibaba", "qwen-turbo", "hi")
except AISDKException as e:
    print("AI错误:", str(e))
except Exception as e:
    print("其他错误:", str(e))
```

- 日志：在 `config/aisdk_config.yaml` 的 `logging` 中配置输出文件、级别与大小滚动。

---

## 目录结构（简要）

```
AI_SDK/
├── __init__.py                 # AISDK 主入口（统一API）
├── core/                       # 领域处理器（llm/asr/tts/multimodal/smart_chat/session等）
├── services/                   # 面向AISDK的服务封装
├── providers/                  # 各家厂商适配（alibaba、deepseek等）
├── utils/                      # 异常、工具、格式化等
└── README.md                   # 本文档
```

---

## 最佳实践

- 使用环境变量注入 API Key（不要把密钥提交到仓库）：
  - Windows PowerShell: `setx ALI_API_KEY "your_key"`
  - Linux/macOS: `export ALI_API_KEY=your_key`
- 覆盖默认配置：初始化时传 `config_dict` 或修改 YAML 中的 `default_params`。
- 控制并发与重试：通过 `request.max_retries`、`timeout`、`retry_delay` 调整。
- 资源清理：处理长会话或高并发时，定期 `list_sessions()` + 清理历史。

---

## 许可证与版本

- 许可证：MIT
- 当前版本：见 `AI_SDK/__init__.py` 中的 `__version__` 