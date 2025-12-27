#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smart Chat 智能对话功能演示程序
展示AI SDK的智能对话功能，包括LLM+TTS的各种组合使用方式
"""

import asyncio
import time
import os
import sys

# 将项目根目录添加到 python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Embodied_SDK.ai import AISDK

# -----------------------------------------------------------------------------


def main():
    """主函数"""
    print("🤖 AI SDK - Smart Chat 智能对话功能演示")
    print("=" * 60)
    print("✨ 特性：一键完成LLM问答+TTS语音播放")
    print("🎵 支持真正的实时流式语音合成")
    print("💬 支持多轮对话和上下文记忆")
    print()
    
    # 初始化SDK
    try:
        sdk = AISDK()
        print("✅ SDK初始化成功")
    except Exception as e:
        print(f"❌ SDK初始化失败: {e}")
        return
    
    while True:
        print("\n📋 请选择功能:")
        print("1. 🎵 真正的实时智能对话")
        print("2. 📝 普通智能对话")
        print("3. 💾 智能对话保存文件")
        print("4. 🔄 多轮对话（上下文记忆）")
        print("5. ⚡ 异步智能对话")
        print("6. 🎭 不同模型组合测试")
        print("7. 📊 功能对比演示")
        print("8. 🧪 批量测试")
        print("0. 退出")
        
        choice = input("\n请输入选择 (0-8): ").strip()
        
        if choice == '0':
            print("👋 再见！")
            break
        elif choice == '1':
            demo_realtime_chat(sdk)
        elif choice == '2':
            demo_normal_chat(sdk)
        elif choice == '3':
            demo_chat_to_file(sdk)
        elif choice == '4':
            demo_context_chat(sdk)
        elif choice == '5':
            asyncio.run(demo_async_chat(sdk))
        elif choice == '6':
            demo_model_combinations(sdk)
        elif choice == '7':
            demo_feature_comparison(sdk)
        elif choice == '8':
            demo_batch_test(sdk)
        else:
            print("❌ 无效选择，请重新输入")


def demo_realtime_chat(sdk):
    """演示真正的实时智能对话"""
    print("\n🎵 真正的实时智能对话演示")
    print("-" * 50)
    print("💡 AI每生成一个字符就立即合成语音，无需等待完整回答")
    print("🚀 使用官方流式TTS API，真正的字符级实时播放")
    
    question = input("\n请输入你的问题: ").strip()
    if not question:
        question = "请详细介绍一下人工智能的发展历程"
    
    print("\n" + "="*60)
    print("🚀 开始真正的实时对话...")
    
    try:
        start_time = time.time()
        
        result = sdk.smart_chat(
            prompt=question,
            stream_chat=True,          # 🔑 启用流式输出
            tts_mode="speaker",        # 🔑 扬声器播放模式
            # llm_provider/model 默认 alibaba/qwen-turbo
            tts_model="cosyvoice-v1",  # 🔑 使用CosyVoice支持真正的流式TTS
            voice="longxiaochun",
            temperature=0.7
        )
        
        end_time = time.time()
        
        if result['success']:
            print(f"\n✅ 真正的实时对话完成!")
            print(f"📝 完整回答: {result['answer'][:100]}...")
            print(f"🤖 LLM: {result['llm_provider']}/{result['llm_model']}")
            print(f"🔊 TTS: {result['tts_provider']}/{result['tts_model']}")
            print(f"🎭 模式: {result['tts_mode']}")
            print(f"⏱️ 总耗时: {end_time - start_time:.2f} 秒")
            
            if 'true_realtime' in result['tts_mode']:
                print("🎉 使用了真正的流式TTS合成!")
            else:
                print("⚠️ 回退到句子分割模式")
        else:
            print(f"❌ 实时对话失败: {result['error']}")
    
    except Exception as e:
        print(f"❌ 对话过程出错: {e}")
    
    print("="*60)


def demo_normal_chat(sdk):
    """演示普通智能对话"""
    print("\n📝 普通智能对话演示")
    print("-" * 50)
    print("💡 等待完整回答后再播放语音，适合稳定性要求高的场景")
    
    question = input("\n请输入你的问题: ").strip()
    if not question:
        question = "请简单介绍一下机器学习"
    
    print("\n" + "="*60)
    print("⏳ 开始普通对话（需等待完整回答）...")
    
    try:
        start_time = time.time()
        
        result = sdk.smart_chat(
            prompt=question,
            stream_chat=False,         # 🔑 不启用流式输出
            # tts_mode 默认为 speaker
            # llm_model 默认为 qwen-turbo
            tts_model="sambert-zhichu-v1",
            temperature=0.7
        )
        
        end_time = time.time()
        
        if result['success']:
            print(f"\n✅ 普通对话完成!")
            print(f"📝 完整回答: {result['answer'][:100]}...")
            print(f"🤖 LLM: {result['llm_provider']}/{result['llm_model']}")
            print(f"🔊 TTS: {result['tts_provider']}/{result['tts_model']}")
            print(f"🎭 模式: {result['tts_mode']}")
            print(f"⏱️ 总耗时: {end_time - start_time:.2f} 秒")
        else:
            print(f"❌ 普通对话失败: {result['error']}")
    
    except Exception as e:
        print(f"❌ 对话过程出错: {e}")
    
    print("="*60)


def demo_chat_to_file(sdk):
    """演示智能对话保存文件"""
    print("\n💾 智能对话保存文件演示")
    print("-" * 50)
    print("💡 流式显示回答过程，但将语音保存为文件")
    
    question = input("\n请输入你的问题: ").strip()
    if not question:
        question = "请创作一首关于春天的诗"
    
    output_file = input("请输入输出文件名 (默认: smart_chat_output.mp3): ").strip()
    if not output_file:
        output_file = "smart_chat_output.mp3"
    
    print("\n" + "="*60)
    print("📁 开始智能对话并保存文件...")
    
    try:
        start_time = time.time()
        
        result = sdk.smart_chat(
            prompt=question,
            stream_chat=True,          # 🔑 启用流式输出
            tts_mode="file",           # 🔑 文件保存模式
            output_file=output_file,
            # llm_model 默认为 qwen-turbo
            tts_model="cosyvoice-v1",
            voice="longxiaochun",
            temperature=0.8
        )
        
        end_time = time.time()
        
        if result['success']:
            print(f"\n✅ 智能对话完成!")
            print(f"📝 完整回答: {result['answer'][:100]}...")
            print(f"📁 文件已保存: {result['tts_result'].get('output_file', '未知')}")
            print(f"🤖 LLM: {result['llm_provider']}/{result['llm_model']}")
            print(f"🔊 TTS: {result['tts_provider']}/{result['tts_model']}")
            print(f"⏱️ 总耗时: {end_time - start_time:.2f} 秒")
        else:
            print(f"❌ 智能对话失败: {result['error']}")
    
    except Exception as e:
        print(f"❌ 对话过程出错: {e}")
    
    print("="*60)


def demo_context_chat(sdk):
    """演示多轮对话（上下文记忆）"""
    print("\n🔄 多轮对话演示（上下文记忆）")
    print("-" * 50)
    print("💡 AI能记住之前的对话内容，支持连续对话")
    
    session_id = f"demo_session_{int(time.time())}"
    print(f"📝 会话ID: {session_id}")
    
    conversation_count = 0
    
    while True:
        conversation_count += 1
        print(f"\n💬 第 {conversation_count} 轮对话")
        
        question = input("请输入你的问题 (输入'退出'结束对话): ").strip()
        if question.lower() in ['退出', 'exit', 'quit', '']:
            break
        
        print("\n" + "="*60)
        print(f"🚀 开始第 {conversation_count} 轮对话...")
        
        try:
            start_time = time.time()
            
            result = sdk.smart_chat(
                prompt=question,
                stream_chat=True,          # 🔑 启用流式输出
                # tts_mode 默认为 speaker
                use_context=True,          # 🔑 启用上下文记忆
                session_id=session_id,     # 🔑 会话ID
                # llm_model 默认为 qwen-turbo
                tts_model="cosyvoice-v1",
                voice="longxiaochun",
                temperature=0.7
            )
            
            end_time = time.time()
            
            if result['success']:
                print(f"\n✅ 第 {conversation_count} 轮对话完成!")
                print(f"📝 AI回答: {result['answer'][:100]}...")
                print(f"⏱️ 耗时: {end_time - start_time:.2f} 秒")
            else:
                print(f"❌ 第 {conversation_count} 轮对话失败: {result['error']}")
        
        except Exception as e:
            print(f"❌ 对话过程出错: {e}")
        
        print("="*60)
    
    print(f"\n🎉 多轮对话结束，共进行了 {conversation_count-1} 轮对话")


async def demo_async_chat(sdk):
    """演示异步智能对话"""
    print("\n⚡ 异步智能对话演示")
    print("-" * 50)
    print("💡 异步版本，性能更好，支持并发处理")
    
    question = input("\n请输入你的问题: ").strip()
    if not question:
        question = "请讲一个关于科技创新的故事"
    
    print("\n" + "="*60)
    print("🚀 开始异步智能对话...")
    
    try:
        start_time = time.time()
        
        result = await sdk.smart_chat(
            prompt=question,
            stream_chat=True,          # 🔑 启用流式输出
            # tts_mode 默认为 speaker
            async_mode=True,           # 🔑 异步模式
            # llm_model 默认为 qwen-turbo
            tts_model="cosyvoice-v1",
            voice="longxiaochun",
            temperature=0.7
        )
        
        end_time = time.time()
        
        if result['success']:
            print(f"\n✅ 异步智能对话完成!")
            print(f"📝 完整回答: {result['answer'][:100]}...")
            print(f"🤖 LLM: {result['llm_provider']}/{result['llm_model']}")
            print(f"🔊 TTS: {result['tts_provider']}/{result['tts_model']}")
            print(f"🎭 模式: {result['tts_mode']}")
            print(f"⏱️ 总耗时: {end_time - start_time:.2f} 秒")
        else:
            print(f"❌ 异步智能对话失败: {result['error']}")
    
    except Exception as e:
        print(f"❌ 异步对话过程出错: {e}")
    
    print("="*60)


def demo_model_combinations(sdk):
    """演示不同模型组合测试"""
    print("\n🎭 不同模型组合测试")
    print("-" * 50)
    print("💡 测试不同LLM和TTS模型的组合效果")
    
    # 测试配置
    test_configs = [
        {
            "name": "通义千问 + CosyVoice",
            "llm_model": "qwen-turbo",
            "tts_model": "cosyvoice-v1",
            "voice": "longxiaochun"
        },
        {
            "name": "通义千问 + Sambert知楚",
            "llm_model": "qwen-turbo", 
            "tts_model": "sambert-zhichu-v1",
            "voice": None
        },
        {
            "name": "通义千问Plus + CosyVoice",
            "llm_model": "qwen-plus",
            "tts_model": "cosyvoice-v1",
            "voice": "longxiaochun"
        }
    ]
    
    question = input("\n请输入测试问题: ").strip()
    if not question:
        question = "请简单介绍一下你自己"
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n🧪 测试 {i}: {config['name']}")
        print("-" * 30)
        
        try:
            start_time = time.time()
            
            kwargs = {
                "prompt": question,
                "stream_chat": True,
                # "tts_mode": "speaker", # 默认
                "llm_model": config["llm_model"],
                "tts_model": config["tts_model"],
                "temperature": 0.7
            }
            
            if config["voice"]:
                kwargs["voice"] = config["voice"]
            
            result = sdk.smart_chat(**kwargs)
            
            end_time = time.time()
            
            if result['success']:
                print(f"✅ 测试成功!")
                print(f"📝 回答长度: {len(result['answer'])} 字符")
                print(f"🎭 TTS模式: {result['tts_mode']}")
                print(f"⏱️ 耗时: {end_time - start_time:.2f} 秒")
            else:
                print(f"❌ 测试失败: {result['error']}")
        
        except Exception as e:
            print(f"❌ 测试过程出错: {e}")
        
        if i < len(test_configs):
            input("\n按回车键继续下一个测试...")


def demo_feature_comparison(sdk):
    """演示功能对比"""
    print("\n📊 功能对比演示")
    print("-" * 50)
    
    print("🎵 真正的实时模式特点:")
    print("   ✅ 使用官方流式TTS API (streaming_call)")
    print("   ✅ AI每生成一个字符就立即合成语音")
    print("   ✅ 无需等待句子完整，字符级实时播放")
    print("   ✅ 用户体验最流畅，感觉AI在实时说话")
    print("   ✅ 适合对话场景和语音助手")
    print("   🔧 需要CosyVoice模型支持")
    print()
    
    print("📝 句子分割模式特点（回退方案）:")
    print("   ⏳ 等待完整句子后再合成播放")
    print("   🎯 按句子播放，语音质量更统一")
    print("   🔧 兼容所有TTS模型")
    print("   💾 内存占用更少")
    print()
    
    print("📝 普通模式特点:")
    print("   ⏳ 等待完整回答后播放")
    print("   📁 适合文件保存")
    print("   🎯 语音质量最统一")
    print("   💾 内存占用最少")
    print()
    
    print("🔧 技术实现对比:")
    print("   真正实时: LLM流式输出 → 字符级TTS流式合成 → 实时播放")
    print("   句子分割: LLM流式输出 → 句子级TTS合成 → 分段播放")
    print("   普通模式: LLM完整输出 → 整体TTS合成 → 一次播放")
    print()
    
    print("🎯 推荐使用场景:")
    print("   真正实时: 语音助手、实时对话、客服机器人")
    print("   句子分割: 教学演示、内容播报、兼容性要求高的场景")
    print("   普通模式: 内容创作、文件保存、长篇文章朗读")
    
    input("\n按回车键返回主菜单...")


def demo_batch_test(sdk):
    """演示批量测试"""
    print("\n🧪 批量测试演示")
    print("-" * 50)
    print("💡 批量测试不同问题的智能对话效果")
    
    test_questions = [
        "你好，请介绍一下你自己",
        "什么是人工智能？",
        "请解释一下机器学习的基本概念",
        "今天天气怎么样？",
        "请推荐一本好书"
    ]
    
    print("📝 测试问题列表:")
    for i, q in enumerate(test_questions, 1):
        print(f"   {i}. {q}")
    
    use_default = input("\n是否使用默认问题列表？(y/n): ").strip().lower()
    
    if use_default != 'y':
        test_questions = []
        print("\n请输入测试问题（输入空行结束）:")
        while True:
            question = input(f"问题 {len(test_questions)+1}: ").strip()
            if not question:
                break
            test_questions.append(question)
    
    if not test_questions:
        print("❌ 没有测试问题")
        return
    
    print(f"\n🚀 开始批量测试 {len(test_questions)} 个问题...")
    
    results = []
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n📝 测试 {i}/{len(test_questions)}: {question}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            
            result = sdk.smart_chat(
                prompt=question,
                stream_chat=True,
                # tts_mode="speaker", # 默认
                # llm_model="qwen-turbo", # 默认
                tts_model="cosyvoice-v1",
                voice="longxiaochun",
                temperature=0.7
            )
            
            end_time = time.time()
            
            if result['success']:
                print(f"✅ 测试 {i} 成功!")
                print(f"📝 回答长度: {len(result['answer'])} 字符")
                print(f"⏱️ 耗时: {end_time - start_time:.2f} 秒")
                
                results.append({
                    'question': question,
                    'success': True,
                    'answer_length': len(result['answer']),
                    'time_cost': end_time - start_time,
                    'tts_mode': result['tts_mode']
                })
            else:
                print(f"❌ 测试 {i} 失败: {result['error']}")
                results.append({
                    'question': question,
                    'success': False,
                    'error': result['error']
                })
        
        except Exception as e:
            print(f"❌ 测试 {i} 出错: {e}")
            results.append({
                'question': question,
                'success': False,
                'error': str(e)
            })
        
        if i < len(test_questions):
            time.sleep(1)  # 短暂休息
    
    # 显示测试总结
    print("\n" + "="*60)
    print("📊 批量测试总结")
    print("="*60)
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"✅ 成功: {success_count}/{total_count}")
    print(f"❌ 失败: {total_count - success_count}/{total_count}")
    print(f"📈 成功率: {success_count/total_count*100:.1f}%")
    
    if success_count > 0:
        successful_results = [r for r in results if r['success']]
        avg_time = sum(r['time_cost'] for r in successful_results) / len(successful_results)
        avg_length = sum(r['answer_length'] for r in successful_results) / len(successful_results)
        
        print(f"⏱️ 平均耗时: {avg_time:.2f} 秒")
        print(f"📝 平均回答长度: {avg_length:.0f} 字符")
        
        # 统计TTS模式
        tts_modes = {}
        for r in successful_results:
            mode = r.get('tts_mode', 'unknown')
            tts_modes[mode] = tts_modes.get(mode, 0) + 1
        
        print("\n🎭 TTS模式统计:")
        for mode, count in tts_modes.items():
            print(f"   {mode}: {count} 次")


if __name__ == "__main__":
    main() 