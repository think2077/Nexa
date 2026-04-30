#!/usr/bin/env python3
"""
Piper TTS 中文语音模型下载工具

由于 HuggingFace 下载可能较慢，本脚本提供多个下载源选择。
"""
import os
import sys
import urllib.request
import urllib.error

# 模型镜像列表
MIRROR_URL = "https://hf-mirror.com"
HF_URL = "https://huggingface.co"

MODEL_FILES = [
    "zh/zh_CN/zh-cnxiaoxiao/high/zh-cnxiaoxiao_high.onnx",
    "zh/zh_CN/zh-cnxiaoxiao/high/zh-cnxiaoxiao_high.onnx.json",
]

def download_file(url, save_path, max_retries=3):
    """下载文件，支持重试"""
    for retry in range(max_retries):
        try:
            print(f"正在下载：{url}")
            print(f"保存至：{save_path}")

            # 创建目录
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 下载
            urllib.request.urlretrieve(url, save_path)

            # 验证
            size = os.path.getsize(save_path)
            if size < 1000:  # 小于 1KB 说明下载失败
                print(f"警告：文件太小 ({size} bytes)，可能下载失败")
                continue

            print(f"✓ 下载完成，大小：{size / 1024 / 1024:.2f} MB")
            return True

        except Exception as e:
            print(f"下载失败 (尝试 {retry + 1}/{max_retries}): {e}")

    return False


def main():
    """主函数"""
    print("=" * 50)
    print("Piper TTS 中文语音模型下载")
    print("=" * 50)
    print()

    # 模型选择
    print("请选择要下载的语音模型:")
    print("  1) zh-cnxiaoxiao - 温柔女声 (推荐)")
    print("  2) zh-cnxiaoyi   - 清晰女声")
    print("  3) zh-cnlibiao   - 成熟男声")
    print()

    choice = input("请选择 [1/2/3] (默认：1): ").strip() or "1"

    model_map = {
        "1": "zh-cnxiaoxiao",
        "2": "zh-cnxiaoyi",
        "3": "zh-cnlibiao",
    }

    if choice not in model_map:
        print("无效选择，使用默认：zh-cnxiaoxiao")
        choice = "1"

    model_name = model_map[choice]

    # 质量选择
    print()
    print("请选择模型质量:")
    print("  1) high   - 高质量 (约 100MB)")
    print("  2) medium - 中等质量 (约 50MB)")
    print("  3) low    - 低质量 (约 20MB)")
    print()

    quality_choice = input("请选择 [1/2/3] (默认：1): ").strip() or "1"

    quality_map = {
        "1": "high",
        "2": "medium",
        "3": "low",
    }

    if quality_choice not in quality_map:
        print("无效选择，使用默认：high")
        quality_choice = "1"

    quality = quality_map[quality_choice]

    # 模型目录
    default_dir = os.path.expanduser("~/piper/models")
    model_dir = input(f"模型保存目录 (默认：{default_dir}): ").strip() or default_dir

    # 构建下载链接
    base_path = f"zh/zh_CN/{model_name}/{quality}"
    onnx_file = f"{model_name}_{quality}.onnx"
    json_file = f"{model_name}_{quality}.onnx.json"

    print()
    print("=" * 50)
    print(f"开始下载：{model_name} ({quality})")
    print("=" * 50)
    print()

    # 尝试主镜像
    print("【尝试 1/3】使用 HF Mirror (hf-mirror.com)...")
    base_url = f"{MIRROR_URL}/rhasspy/piper-voices/resolve/main/{base_path}"

    success = True
    for filename in [onnx_file, json_file]:
        url = f"{base_url}/{filename}"
        save_path = os.path.join(model_dir, filename)

        if not download_file(url, save_path):
            success = False
            break

    # 尝试备用源
    if not success:
        print()
        print("【尝试 2/3】使用 HuggingFace 主站...")
        base_url = f"{HF_URL}/rhasspy/piper-voices/resolve/main/{base_path}"

        success = True
        for filename in [onnx_file, json_file]:
            url = f"{base_url}/{filename}"
            save_path = os.path.join(model_dir, filename)

            if not download_file(url, save_path):
                success = False
                break

    # 最终提示
    print()
    print("=" * 50)

    if success:
        print("✓ 下载完成!")
        print()
        print(f"模型文件：{os.path.join(model_dir, onnx_file)}")
        print(f"配置文件：{os.path.join(model_dir, json_file)}")
        print()
        print("请在 .env 文件中添加:")
        print(f"  PIPER_MODEL_PATH={os.path.join(model_dir, onnx_file)}")
        print(f"  PIPER_CONFIG_PATH={os.path.join(model_dir, json_file)}")
        print()

        # 测试
        test = input("是否现在测试语音合成？[y/N] (需要 piper-tts 已安装): ").strip().lower()
        if test == 'y':
            try:
                from piper import PiperVoice
                voice = PiperVoice.load(os.path.join(model_dir, onnx_file))
                print("✓ 模型加载成功!")

                test_text = "你好，这是 Piper 语音合成测试。我是" + model_name + "，很高兴为你服务。"
                print(f"合成文本：{test_text}")

                # 合成并播放（需要 pyaudio）
                audio_chunks = []
                for chunk in voice.synthesize(test_text):
                    audio_chunks.append(chunk)

                if audio_chunks:
                    print(f"✓ 合成成功！音频大小：{sum(len(c) for c in audio_chunks) / 1024:.1f} KB")
                    print("  (播放功能需要安装 pyaudio: pip3 install pyaudio)")
                else:
                    print("✗ 合成失败：未生成音频")

            except ImportError:
                print("piper-tts 未安装，跳过测试")
            except Exception as e:
                print(f"测试失败：{e}")
    else:
        print("✗ 下载失败，请检查网络连接后重试")
        print("或者手动从 https://huggingface.co/rhasspy/piper-voices 下载")

    print("=" * 50)


if __name__ == "__main__":
    main()
