#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态功能演示程序
展示AI SDK的图像和视频理解功能

功能包括：
1. 图像理解 - 分析单张图片
2. 多图像分析 - 比较多张图片
3. 视频理解 - 分析视频内容
4. 流式图像对话 - 实时图像理解对话
5. 异步多模态调用
6. 高级多模态对话
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
        if 'response' in result:
            # 标准响应格式
            response = result['response']
            content = response['choices'][0]['message']['content']
            print(f"回答: {content}")
            
            if 'usage' in response:
                usage = response['usage']
                print(f"\nToken使用情况:")
                if isinstance(usage, dict):
                    for key, value in usage.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"  {usage}")
            
            if 'processing_time' in result:
                print(f"处理时间: {result['processing_time']:.2f}秒")
        else:
            # 直接结果
            print(f"结果: {result}")
    else:
        print(f"❌ 错误: {result.get('error', '未知错误')}")

def demo_image_analysis(sdk):
    """演示图像分析功能"""
    print_separator("图像分析演示")
    
    # 使用在线图片URL进行演示
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    prompt = "请详细描述这张图片中的内容，包括人物、动物、环境等"
    
    print(f"📸 分析图片: {image_url}")
    print(f"🤔 提问: {prompt}")
    
    try:
        result = self.sdk.multimodal(
            prompt=prompt,
            mode="image",
            image_path=image_url,
            model="qwen-vl-max-latest",
            temperature=0.7
        )
        print_result(result, "图像分析结果")
        
    except Exception as e:
        print(f"❌ 图像分析失败: {str(e)}")

def demo_multiple_images_analysis(sdk):
    """演示多图像分析功能"""
    print_separator("多图像分析演示")
    
    # 使用多张在线图片URL
    image_urls = [
        "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg",
        "https://dashscope.oss-cn-beijing.aliyuncs.com/images/tiger.png"
    ]
    prompt = "请比较这两张图片的内容，说明它们的相同点和不同点"
    
    print(f"📸 分析多张图片:")
    for i, url in enumerate(image_urls, 1):
        print(f"  图片{i}: {url}")
    print(f"🤔 提问: {prompt}")
    
    try:
        result = self.sdk.multimodal(
            prompt=prompt,
            mode="multiple_images",
            image_paths=image_urls,
            model="qwen-vl-max-latest"
        )
        print_result(result, "多图像分析结果")
        
    except Exception as e:
        print(f"❌ 多图像分析失败: {str(e)}")

def demo_video_analysis(sdk):
    """演示视频分析功能"""
    print_separator("视频分析演示")
    
    # 使用在线视频URL
    video_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241115/cqqkru/1.mp4"
    prompt = "请分析这个视频的内容，描述视频中发生了什么"
    
    print(f"🎥 分析视频: {video_url}")
    print(f"🤔 提问: {prompt}")
    
    try:
        result = self.sdk.multimodal(
            prompt=prompt,
            mode="video",
            video_path=video_url,
            model="qwen-vl-max-latest",
            fps=0.5  # 每0.5秒抽取一帧
        )
        print_result(result, "视频分析结果")
        
    except Exception as e:
        print(f"❌ 视频分析失败: {str(e)}")

def demo_streaming_image_chat(sdk):
    """演示流式图像对话"""
    print_separator("流式图像对话演示")
    
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    
    # 准备消息格式
    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                },
                {"type": "text", "text": "请用诗歌的形式描述这张图片"}
            ]
        }
    ]
    
    print(f"📸 图片: {image_url}")
    print(f"🤔 要求: 请用诗歌的形式描述这张图片")
    print("\n🌊 流式输出:")
    print("-" * 40)
    
    try:
        full_content = ""
        for chunk in sdk.multimodal_handler.chat_with_image_stream("alibaba", messages):
            if 'choices' in chunk and chunk['choices'][0].get('delta', {}).get('content'):
                content = chunk['choices'][0]['delta']['content']
                print(content, end='', flush=True)
                full_content += content
        
        print(f"\n\n完整内容:\n{full_content}")
        
    except Exception as e:
        print(f"❌ 流式图像对话失败: {str(e)}")

async def demo_async_multimodal(sdk):
    """演示异步多模态调用"""
    print_separator("异步多模态调用演示")
    
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    prompt = "这张图片给你什么感受？请用感性的语言描述"
    
    print(f"📸 异步分析图片: {image_url}")
    print(f"🤔 提问: {prompt}")
    print("⏳ 异步处理中...")
    
    try:
        start_time = time.time()
        result = await self.sdk.multimodal(
            prompt=prompt,
            mode="image",
            image_path=image_url,
            async_mode=True,
            model="qwen-vl-max-latest"
        )
        end_time = time.time()
        
        print(f"⚡ 异步调用完成，耗时: {end_time - start_time:.2f}秒")
        print_result(result, "异步分析结果")
        
    except Exception as e:
        print(f"❌ 异步多模态调用失败: {str(e)}")

def demo_advanced_multimodal_chat(sdk):
    """演示高级多模态对话"""
    print_separator("高级多模态对话演示")
    
    image_url = "https://help-static-aliyun-doc.aliyuncs.com/file-manage-files/zh-CN/20241022/emyrja/dog_and_girl.jpeg"
    
    # 多轮对话
    conversations = [
        "请描述这张图片中的场景",
        "图片中的人和狗的关系如何？",
        "这个场景给人什么样的感觉？",
        "如果你要给这张照片起个标题，会叫什么？"
    ]
    
    print(f"📸 图片: {image_url}")
    print("🗣️ 开始多轮对话:")
    
    # 初始消息
    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": "You are a helpful assistant."}]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url}
                },
                {"type": "text", "text": conversations[0]}
            ]
        }
    ]
    
    try:
        for i, question in enumerate(conversations, 1):
            print(f"\n第{i}轮对话:")
            print(f"👤 用户: {question}")
            
            if i > 1:
                # 添加新的用户消息
                messages.append({
                    "role": "user",
                    "content": [{"type": "text", "text": question}]
                })
            
            # 获取AI回答
            result = sdk.multimodal_handler.chat_with_image("alibaba", messages)
            
            if result.get('success', True) and 'response' in result:
                content = result['response']['choices'][0]['message']['content']
                print(f"🤖 AI: {content}")
                
                # 添加AI回答到对话历史
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": content}]
                })
            else:
                print(f"❌ 第{i}轮对话失败: {result.get('error', '未知错误')}")
                break
                
    except Exception as e:
        print(f"❌ 高级多模态对话失败: {str(e)}")

def demo_local_file_analysis(sdk):
    """演示本地文件分析（如果有本地文件）"""
    print_separator("本地文件分析演示")
    
    # 检查是否有本地测试图片
    test_images = ["test_image.jpg", "test_image.png", "sample.jpg", "sample.png"]
    local_image = None
    
    for img in test_images:
        if os.path.exists(img):
            local_image = img
            break
    
    if local_image:
        print(f"📸 发现本地图片: {local_image}")
        prompt = "请分析这张本地图片的内容"
        
        try:
            result = self.sdk.multimodal(
                prompt=prompt,
                mode="image",
                image_path=local_image,
                model="qwen-vl-max-latest"
            )
            print_result(result, "本地图片分析结果")
            
        except Exception as e:
            print(f"❌ 本地图片分析失败: {str(e)}")
    else:
        print("📸 未找到本地测试图片")
        print("💡 提示: 可以将图片文件放在当前目录下，命名为 test_image.jpg 或 test_image.png")

def show_menu():
    """显示菜单"""
    print("\n" + "="*60)
    print(" AI SDK 多模态功能演示")
    print("="*60)
    print("1. 图像分析演示")
    print("2. 多图像分析演示") 
    print("3. 视频分析演示")
    print("4. 流式图像对话演示")
    print("5. 异步多模态调用演示")
    print("6. 高级多模态对话演示")
    print("7. 本地文件分析演示")
    print("8. 运行所有演示")
    print("0. 退出")
    print("="*60)

async def main():
    """主函数"""
    print("🚀 初始化AI SDK...")
    
    try:
        # 初始化SDK
        sdk = AISDK()
        print("✅ AI SDK初始化成功")
        
        while True:
            show_menu()
            choice = input("\n请选择功能 (0-8): ").strip()
            
            if choice == "0":
                print("👋 再见！")
                break
            elif choice == "1":
                demo_image_analysis(sdk)
            elif choice == "2":
                demo_multiple_images_analysis(sdk)
            elif choice == "3":
                demo_video_analysis(sdk)
            elif choice == "4":
                demo_streaming_image_chat(sdk)
            elif choice == "5":
                await demo_async_multimodal(sdk)
            elif choice == "6":
                demo_advanced_multimodal_chat(sdk)
            elif choice == "7":
                demo_local_file_analysis(sdk)
            elif choice == "8":
                print("🎯 运行所有演示...")
                demo_image_analysis(sdk)
                demo_multiple_images_analysis(sdk)
                demo_video_analysis(sdk)
                demo_streaming_image_chat(sdk)
                await demo_async_multimodal(sdk)
                demo_advanced_multimodal_chat(sdk)
                demo_local_file_analysis(sdk)
                print("\n🎉 所有演示完成！")
            else:
                print("❌ 无效选择，请重新输入")
            
            input("\n按回车键继续...")
            
    except Exception as e:
        print(f"❌ 程序运行出错: {str(e)}")
        print("💡 请检查配置文件和网络连接")

if __name__ == "__main__":
    asyncio.run(main()) 