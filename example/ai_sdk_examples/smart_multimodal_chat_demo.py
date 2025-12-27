#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态智能对话演示程序
展示AI SDK的流式图像理解对话并实时语音播放功能

功能包括：
1. 图像理解智能对话 - 分析图片并实时语音播放
2. 视频分析智能对话 - 分析视频并实时语音播放
3. 多图像比较智能对话 - 比较多张图片并实时语音播放
4. 流式输出模式 - 实时显示AI思考过程
5. 语音文件保存模式 - 将分析结果保存为音频文件
6. 异步调用模式 - 异步处理多模态对话
"""

import os
import sys
import asyncio
import time

# 将项目根目录添加到 python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Embodied_SDK.ai import AISDK

# -----------------------------------------------------------------------------

def print_separator(title=""):
    """打印分隔线"""
    print("\n" + "="*60)
    if title:
        print(f" {title} ")
        print("="*60)

def print_result(result, title="结果"):
    """格式化打印结果"""
    print(f"\n{title}:")
    print("-" * 40)
    
    if result.get('success', True):
        print(f"状态: 成功")
        print(f"回答: {result.get('answer', '无回答')}")
        print(f"媒体类型: {result.get('mode', '未知')}")
        print(f"媒体信息: {result.get('media_info', '未知')}")
        print(f"多模态提供商: {result.get('multimodal_provider', '未知')}")
        print(f"TTS提供商: {result.get('tts_provider', '未知')}")
        print(f"TTS模式: {result.get('tts_mode', '未知')}")
        
        if 'tts_result' in result:
            tts_result = result['tts_result']
            if tts_result.get('success'):
                print(f"语音合成: 成功")
                if 'output_file' in tts_result:
                    print(f"输出文件: {tts_result['output_file']}")
            else:
                print(f"语音合成: 失败 - {tts_result.get('error', '未知错误')}")
    else:
        print(f"错误: {result.get('error', '未知错误')}")

def demo_image_smart_chat(sdk):
    """演示图像智能对话"""
    print_separator("图像智能对话演示")
    
    # 使用在线图片URL进行演示
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    prompt = "请详细描述这张图片中的内容，包括人物、动物、环境等，并分析这个场景传达的情感"
    
    print(f"图片: {image_url}")
    print(f"提问: {prompt}")
    print("开始流式图像理解对话 + 实时语音播放...")
    
    try:
        result = sdk.smart_multimodal_chat(
            prompt=prompt,
            image_path=image_url,
            multimodal_model="qwen-vl-max-latest",
            tts_model="cosyvoice-v1",
            stream_output=True,
            realtime_tts=True,
            temperature=0.7,
            voice="longxiaochun"  # CosyVoice模型的音色
        )
        print_result(result, "图像智能对话结果")
        
    except Exception as e:
        print(f"图像智能对话失败: {str(e)}")

def demo_video_smart_chat(sdk):
    """演示视频智能对话"""
    print_separator("视频智能对话演示")
    
    # 使用在线视频URL
    video_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241115/cqqkru/1.mp4"
    prompt = "请分析这个视频的内容，描述视频中发生了什么，并解释其意义"
    
    print(f"视频: {video_url}")
    print(f"提问: {prompt}")
    print("开始流式视频分析对话 + 实时语音播放...")
    
    try:
        result = sdk.smart_multimodal_chat(
            prompt=prompt,
            video_path=video_url,
            # multimodal_model 默认 qwen-vl-max-latest
            # tts_model 默认 sambert-zhichu-v1
            stream_output=True,
            realtime_tts=True,
            fps=0.5
        )
        print_result(result, "视频智能对话结果")
        
    except Exception as e:
        print(f"视频智能对话失败: {str(e)}")

def demo_multiple_images_smart_chat(sdk):
    """演示多图像智能对话"""
    print_separator("多图像智能对话演示")
    
    # 使用多张在线图片URL
    image_urls = [
        "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg",
        "https://dashscope.oss-cn-beijing.aliyuncs.com/images/tiger.png"
    ]
    prompt = "请比较这两张图片的内容，分析它们的相同点和不同点，并说明各自的特色"
    
    print(f"图片数量: {len(image_urls)}")
    for i, url in enumerate(image_urls, 1):
        print(f"  图片{i}: {url}")
    print(f"提问: {prompt}")
    print("开始流式多图像比较对话 + 实时语音播放...")
    
    try:
        result = sdk.smart_multimodal_chat(
            prompt=prompt,
            image_paths=image_urls,
            # multimodal_model 默认 qwen-vl-max-latest
            # tts_model 默认 sambert-zhichu-v1
            stream_output=True,
            realtime_tts=True
        )
        print_result(result, "多图像智能对话结果")
        
    except Exception as e:
        print(f"多图像智能对话失败: {str(e)}")

def demo_save_to_file_mode(sdk):
    """演示保存语音文件模式"""
    print_separator("语音文件保存模式演示")
    
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    prompt = "请用诗歌的形式描述这张图片，要求语言优美，富有感情"
    output_file = "image_analysis_poem.mp3"
    
    print(f"图片: {image_url}")
    print(f"提问: {prompt}")
    print(f"输出文件: {output_file}")
    print("开始流式图像理解对话 + 语音文件保存...")
    
    try:
        result = sdk.smart_multimodal_chat(
            prompt=prompt,
            image_path=image_url,
            tts_mode="file",
            output_file=output_file,
            stream_output=True,
            realtime_tts=False,  # 文件模式不需要实时播放
            # tts_model 默认 sambert-zhichu-v1
            voice="zhixiaoxia"  # Sambert模型的温柔女声
        )
        print_result(result, "语音文件保存结果")
        
        # 检查文件是否生成
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"文件已生成: {output_file} ({file_size} 字节)")
        
    except Exception as e:
        print(f"语音文件保存失败: {str(e)}")

def demo_non_streaming_mode(sdk):
    """演示非流式模式"""
    print_separator("非流式模式演示")
    
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    prompt = "请简洁地描述这张图片的主要内容"
    
    print(f"图片: {image_url}")
    print(f"提问: {prompt}")
    print("开始非流式图像理解对话 + 语音播放...")
    
    try:
        result = sdk.smart_multimodal_chat(
            prompt=prompt,
            image_path=image_url,
            stream_output=False,  # 关闭流式输出
            realtime_tts=False,   # 关闭实时TTS
            tts_mode="speaker"
        )
        print_result(result, "非流式模式结果")
        
    except Exception as e:
        print(f"非流式模式失败: {str(e)}")

async def demo_async_smart_chat(sdk):
    """演示异步智能对话"""
    print_separator("异步智能对话演示")
    
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    prompt = "这张图片给你什么感受？请用感性的语言描述"
    
    print(f"异步分析图片: {image_url}")
    print(f"提问: {prompt}")
    print("异步处理中...")
    
    try:
        start_time = time.time()
        result = await sdk.smart_multimodal_chat(
            prompt=prompt,
            image_path=image_url,
            async_mode=True,
            stream_output=False,
            realtime_tts=False
        )
        end_time = time.time()
        
        print(f"异步调用完成，耗时: {end_time - start_time:.2f}秒")
        print_result(result, "异步智能对话结果")
        
    except Exception as e:
        print(f"异步智能对话失败: {str(e)}")

def demo_custom_voice_and_model(sdk):
    """演示自定义音色和模型"""
    print_separator("自定义音色和模型演示")
    
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    prompt = "请用温柔的语调描述这张图片中的温馨场景"
    
    print(f"图片: {image_url}")
    print(f"提问: {prompt}")
    print("使用自定义音色: longxiaochun (CosyVoice音色)")
    print("开始自定义模式智能对话...")
    
    try:
        result = sdk.smart_multimodal_chat(
            prompt=prompt,
            image_path=image_url,
            multimodal_model="qwen-vl-plus-latest",  # 使用plus模型
            tts_model="cosyvoice-v1",                # 使用cosyvoice
            voice="longxiaochun",                    # CosyVoice音色
            stream_output=True,
            realtime_tts=True,
            temperature=0.8
        )
        print_result(result, "自定义模式结果")
        
    except Exception as e:
        print(f"自定义模式失败: {str(e)}")

def show_menu():
    """显示菜单"""
    print("\n" + "="*60)
    print(" AI SDK 多模态智能对话演示")
    print("="*60)
    print("1. 图像智能对话演示 (流式 + 实时语音)")
    print("2. 视频智能对话演示 (流式 + 实时语音)")
    print("3. 多图像智能对话演示 (流式 + 实时语音)")
    print("4. 语音文件保存模式演示")
    print("5. 非流式模式演示")
    print("6. 异步智能对话演示")
    print("7. 自定义音色和模型演示")
    print("8. 运行所有演示")
    print("0. 退出")
    print("="*60)
    print("提示: 实时语音播放需要扬声器设备")

async def main():
    """主函数"""
    print("初始化AI SDK...")
    
    try:
        # 初始化SDK
        sdk = AISDK()
        print("AI SDK初始化成功")
        
        while True:
            show_menu()
            choice = input("\n请选择功能 (0-8): ").strip()
            
            if choice == "0":
                print("再见！")
                break
            elif choice == "1":
                demo_image_smart_chat(sdk)
            elif choice == "2":
                demo_video_smart_chat(sdk)
            elif choice == "3":
                demo_multiple_images_smart_chat(sdk)
            elif choice == "4":
                demo_save_to_file_mode(sdk)
            elif choice == "5":
                demo_non_streaming_mode(sdk)
            elif choice == "6":
                await demo_async_smart_chat(sdk)
            elif choice == "7":
                demo_custom_voice_and_model(sdk)
            elif choice == "8":
                print("运行所有演示...")
                demo_image_smart_chat(sdk)
                demo_video_smart_chat(sdk)
                demo_multiple_images_smart_chat(sdk)
                demo_save_to_file_mode(sdk)
                demo_non_streaming_mode(sdk)
                await demo_async_smart_chat(sdk)
                demo_custom_voice_and_model(sdk)
                print("\n所有演示完成！")
            else:
                print("无效选择，请重新输入")
            
            input("\n按回车键继续...")
            
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
        print("请检查配置文件和网络连接")

if __name__ == "__main__":
    asyncio.run(main()) 