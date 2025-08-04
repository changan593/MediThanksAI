import pandas as pd
import os
from itertools import product, chain, combinations

# 基础提示语
BASE_PROMPT = ""

# 每个选项对应的提示词部分
OPTION_PROMPTS = {
    # 视角选项
    'doctor_centered': (
        "以医生为中心，结合医生的背景、专业领域和擅长的疾病，强调医生在该领域的专业性和丰富经验对诊疗的重要性,"
        "突出医生的专业能力和个人品质，表达对医生付出的高度认可。"
    ),
    'patient_centered': (
        "以患者为中心，强调医生的帮助对患者的意义，医生的行为如何帮助患者克服困难，突出医生的利他行为。"
    ),
    
    # 导向选项
    'process_oriented': (
        "以过程为导向，提及治疗过程中医生帮助你理解病情并有效应对的具体场景，包括医生如何通过其行动或言语来帮助的，"
        "描绘诊疗情境，阐述这些行为如何积极影响了你的就医体验。"
    ),
    'result_oriented': (
        "以结果为导向，描述在接受诊疗后的健康状况变化及治疗效果，"
        "包括医生所采取的治疗方案或给予的建议如何帮助实现预期效果，"
        "同时，试着表达在治疗结束后对疗效的感受。"
    ),
    
    # 个性化选项
    'personalized': (
        "增强患者感激表达的个性化程度，内容中要多次提及‘医生姓氏’，"
        "并结合医生职称使用不同的称谓,结合给出的医生背景信息来增加个性化内容。"
    ),
    'impersonalized': (
        "使用真诚的语言表达对医生的感谢，关注医生共性的职业特质，无需提及具体医生姓名、职称及其他具体信息。"
    ),
    
    # 情感选项
    'emotional_intensity': (
        "加深患者感激之情表达的情感强度，展现医生治疗过程中的服务表现，适当使用赞美医生的词语或成语。"
    ),
    'general_emotion': (
        "使用简洁的语言表达对医生的感谢，关注医生共性的职业特质，无需使用过多的赞美词语或过度修饰。"
    ),

    # 风格选项
    'formal': (
        "以正式语言风格撰写一段感谢语，使用庄重、礼貌的表达方式，突出对医生专业性和敬业精神的高度认可，"
        "并适当加入书面语或成语，体现对医生的尊重与感激。"
    ),
    'colloquial': (
        "以口语化语言风格撰写一段感谢语，使用自然、亲切的表达方式，突出对医生关怀和帮助的真诚感激，"
        "语言轻松活泼，并适当加入感叹词或口语化短语，体现与医生的亲近感。"
    ),
    
}

# 定义每组选项
OPTION_GROUPS = {
    'perspective': ['doctor_centered', 'patient_centered'],
    'orientation': ['process_oriented', 'result_oriented'],
    'personalization': ['personalized', 'impersonalized'],
    'emotion_strength': ['emotional_intensity', 'general_emotion'],
    'style': ['formal', 'colloquial']
}

def get_all_valid_combinations():
    # 获取每组的所有可能选择（不包括不选）
    group_choices = []
    for group_options in OPTION_GROUPS.values():
        # 只添加选项，不添加 None
        group_choices.append(group_options)
    
    # 生成所有可能的组合
    all_combinations = list(product(*group_choices))
    
    # 过滤掉全是 None 的组合（至少要选一个选项）
    valid_combinations = [
        combo for combo in all_combinations 
        if all(option is not None for option in combo)  # 确保每组都有选项
    ]
    
    # 将组合转换为选项字符串列表
    result = []
    for combo in valid_combinations:
        # 只包含非 None 的选项
        options = [opt for opt in combo]
        # 按字母顺序排序以保持一致性
        options.sort()
        result.append(','.join(options))
    
    return result

# 创建提示词数据
data = {
    'option_combination': get_all_valid_combinations()
}

# 生成提示词模板
data['prompt_template'] = []
for combination in data['option_combination']:
    options = combination.split(',')
    prompt = BASE_PROMPT
    for option in options:
        prompt += OPTION_PROMPTS[option]
    prompt += "\n下面给出了可参考的患者和医生信息，以及需要润色的感谢语。\n"
    data['prompt_template'].append(prompt)

# 创建DataFrame
df = pd.DataFrame(data)

# 保存为Excel文件
try:
    # 检查文件是否存在
    if os.path.exists('prompts.xlsx'):
        print("文件已存在，尝试删除...")
        try:
            os.remove('prompts.xlsx')
            print("成功删除旧文件")
        except Exception as e:
            print(f"删除文件失败: {e}")
            print("请确保 prompts.xlsx 未被其他程序打开")
            exit(1)
    
    # 保存新文件
    print("正在保存新的提示词模板...")
    df.to_excel('prompts.xlsx', index=False)
    print("提示词模板文件已成功创建：prompts.xlsx")
    
    # 打印统计信息
    print(f"\n总共生成了 {len(data['option_combination'])} 种组合")
    print("\n示例组合：")
    for i, combo in enumerate(data['option_combination'][:5]):
        print(f"{i+1}. {combo}")
    
    # 验证文件是否正确保存
    try:
        verification_df = pd.read_excel('prompts.xlsx')
        print(f"\n文件已保存，包含 {len(verification_df)} 行数据")
    except Exception as e:
        print(f"验证文件失败: {e}")

except Exception as e:
    print(f"保存文件时发生错误: {e}")
    print("请检查是否有写入权限或文件是否被占用")
    