from flask import Flask, render_template, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pandas as pd
import json
from openai import OpenAI  # 用于 Deepseek API
from io import BytesIO
import pytz  # 添加这行
from functools import wraps
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///thankyou_letters.db'
app.config['DEEPSEEK_API_KEY'] = os.getenv('DEEPSEEK_API_KEY')
# app.config['DEEPSEEK_API_KEY'] = 'sk-d9eede3ed8514a39a76522d10283e0c7'  # 替换为一会儿师姐给你的API密钥
client = OpenAI(
    api_key=app.config['DEEPSEEK_API_KEY'],
    base_url="https://api.deepseek.com"
)
db = SQLAlchemy(app)

# 添加一个简单的管理token
ADMIN_TOKEN = "dsfgajfghdsf548431"  # 建议使用随机生成的复杂字符串

# 简单的认证装饰器
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.args.get('token')
        if token != ADMIN_TOKEN:
            return "未授权访问", 403
        return f(*args, **kwargs)
    return decorated_function

# 加载提示词模板
def load_prompts():
    print("\n=== 开始加载提示词模板 ===")
    df = pd.read_excel('prompts.xlsx')
    print("\nExcel文件内容预览:")
    print(df.head(1))
    
    prompts_dict = {}
    for _, row in df.iterrows():
        option_key = row['option_combination']
        prompts_dict[option_key] = row['prompt_template']
        #print(f"\n选项组合: {option_key}")
        #print(f"对应模板: {prompts_dict[option_key][:100]}...")  # 只打印前100个字符
    
    print(f"\n总共加载了 {len(prompts_dict)} 个提示词模板")
    return prompts_dict

PROMPTS = load_prompts()

# 数据模型
class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100))
    gender = db.Column(db.String(10))
    age = db.Column(db.String(10))
    disease = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))

    def __repr__(self):
        return f'<Patient {self.patient_name}>'

class Letter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))  # 添加患者ID外键
    patient_name = db.Column(db.String(100))
    gender = db.Column(db.String(10))
    age = db.Column(db.String(10))
    disease = db.Column(db.String(200))
    doctor_name = db.Column(db.String(100))
    doctor_title = db.Column(db.String(100))
    doctor_department = db.Column(db.String(100))
    doctor_gender = db.Column(db.String(10))
    hospital = db.Column(db.String(100))
    original_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))

class PolishHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    letter_id = db.Column(db.Integer, db.ForeignKey('letter.id'))
    previous_text = db.Column(db.Text)  # 润色前的文本
    polished_text = db.Column(db.Text)  # 润色后的文本
    polish_options = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))

# 添加新的数据模型
class AdoptedPolish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))  # 新增患者ID字段
    letter_id = db.Column(db.Integer, db.ForeignKey('letter.id'))
    polish_id = db.Column(db.Integer, db.ForeignKey('polish_history.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))

class UserAction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'))  # 添加患者ID外键
    patient_name = db.Column(db.String(100))
    gender = db.Column(db.String(10))
    age = db.Column(db.String(10))
    disease = db.Column(db.String(200))
    action_type = db.Column(db.String(50))
    action_detail = db.Column(db.Text)
    letter_id = db.Column(db.Integer)
    polish_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Shanghai')))

    def __repr__(self):
        return f'<UserAction {self.patient_name} {self.action_type}>'

# 添加记录用户行为的函数
def record_user_action(data, action_type, action_detail="", letter_id=None, polish_id=None, patient_id=None):
    try:
        user_action = UserAction(
            patient_id=patient_id,
            patient_name=data.get('patient_name'),
            gender=data.get('gender'),
            age=data.get('age'),
            disease=data.get('disease'),
            action_type=action_type,
            action_detail=action_detail,
            letter_id=letter_id,
            polish_id=polish_id
        )
        db.session.add(user_action)
        db.session.commit()
        print(f"记录用户行为成功: {action_type}, 患者ID: {patient_id}")
    except Exception as e:
        print(f"记录用户行为失败: {str(e)}")
        db.session.rollback()

@app.route('/')
def index():
    
    return render_template('index.html')

@app.route('/submit_letter', methods=['POST'])
def submit_letter():
    try:
        data = request.json
        
        # 验证年龄
        age = int(data['age'])
        if age < 0:
            raise ValueError("年龄不能为负数")
            
        # 创建新的感谢信记录
        letter = Letter(
            patient_name=data['patient_name'],
            gender=data['gender'],
            age=age,  # 使用验证后的年龄
            disease=data['disease'],
            doctor_name=data['doctor_name'],
            doctor_title=data['doctor_title'],
            doctor_department=data['doctor_department'],
            doctor_gender=data['doctor_gender'],
            hospital=data['hospital'],
            original_text=data['original_text']
        )
        db.session.add(letter)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'letter_id': letter.id
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/polish_letter', methods=['POST'])
def polish_letter():
    try:
        data = request.json
        print("\n=== 开始润色请求 ===")
        print("润色基础:", data.get('polish_base'))
        print("选中的润色ID:", data.get('previous_polish_id'))

        # 查找或创建患者记录（只通过姓名、性别、年龄判断）
        patient = Patient.query.filter_by(
            patient_name=data['patient_name'],
            gender=data['gender'],
            age=data['age']
        ).first()

        if not patient:
            patient = Patient(
                patient_name=data['patient_name'],
                gender=data['gender'],
                age=data['age'],
                disease=data['disease']  # 仍然保存疾病信息，但不用于判断
            )
            db.session.add(patient)
            db.session.commit()
            print(f"创建新患者记录，ID: {patient.id}")
        else:
            print(f"找到现有患者记录，ID: {patient.id}")

        # 查找是否存在相同内容的感谢信记录
        letter = Letter.query.filter_by(
            patient_id=patient.id,
            doctor_name=data['doctor_name'],
            doctor_title=data['doctor_title'],
            doctor_department=data['doctor_department'],
            doctor_gender=data['doctor_gender'],
            hospital=data['hospital'],
            original_text=data['original_text']
        ).first()

        # 如果不存在，创建新记录
        if not letter:
            letter = Letter(
                patient_id=patient.id,
                patient_name=data['patient_name'],
                gender=data['gender'],
                age=data['age'],
                disease=data['disease'],
                doctor_name=data['doctor_name'],
                doctor_title=data['doctor_title'],
                doctor_department=data['doctor_department'],
                doctor_gender=data['doctor_gender'],
                hospital=data['hospital'],
                original_text=data['original_text']
            )
            db.session.add(letter)
            db.session.commit()

        # 确定要润色的文本
        if data.get('polish_base') == 'previous' and data.get('previous_polish_id'):
            previous_polish = PolishHistory.query.get(data['previous_polish_id'])
            if previous_polish:
                text_to_polish = previous_polish.polished_text  # 使用选中的润色结果作为要润色的文本
                print("使用之前的润色结果:", text_to_polish[:100], "...")
            else:
                raise ValueError("未找到指定的润色记录")
        else:
            text_to_polish = data['original_text']  # 使用原始文本
            print("使用原始文本:", text_to_polish[:100], "...")

        # 获取选择的润色选项
        polish_options = sorted(data['polish_options'])
        option_key = ','.join(polish_options)
        print("润色选项:", option_key)

        # 获取对应的提示词模板
        prompt_template = PROMPTS.get(option_key)
        if not prompt_template:
            print("3. 警告：未找到对应的提示词模板，使用默认模板")
            prompt_template = "请润色以下感谢信，保持原意的同时使其更加{}"
        print("3. 使用的提示词模板:", prompt_template)
        
        # 构建提示词
        system_prompt = "你是一个专业的医患沟通顾问，擅长润色感谢信。"
        user_prompt = f"""
            润色要求：
            {prompt_template}

            以下是需要润色的感谢信的背景信息：

            患者信息：
            - 姓名：{data['patient_name']}
            - 性别：{data['gender']}
            - 年龄：{data['age']}岁
            - 疾病：{data['disease']}

            医生信息：
            - 姓名：{data['doctor_name']}
            - 职称：{data['doctor_title']}
            - 科室：{data['doctor_department']}
            - 性别：{data['doctor_gender']}
            - 医院：{data['hospital']}

            需要润色的内容：
            {text_to_polish}


            请根据以上要求和信息对需要润色的内容进行润色，保持语境一致，语义不变，简洁明了，逻辑清晰，易于理解，避免模板化和书面化，注意避免重复之前的表达。
            只需要按以上要求输出改写后的语句即可。生成的感谢语不要用特殊字符标出患者和医生的个人信息。
        """
        print("5. 发送给API的提示词:", user_prompt)
        
        try:
            # 调用 Deepseek API
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False
            )
            print("6. API调用成功")
            
        except Exception as api_error:
            print("6. API调用失败:", str(api_error))
            raise api_error
        
        polished_text = response.choices[0].message.content
        print("7. API返回的结果长度:", len(polished_text))
        
        # 记录润色历史
        polish_history = PolishHistory(
            letter_id=letter.id,
            polish_options=option_key,
            previous_text=text_to_polish,  # 使用实际润色的文本作为previous_text
            polished_text=polished_text
        )
        db.session.add(polish_history)
        db.session.commit()
        
        # 记录润色行为
        record_user_action(
            data=data,
            action_type='click_polish',
            action_detail=f"选项: {','.join(data['polish_options'])}",
            letter_id=letter.id,
            polish_id=polish_history.id,
            patient_id=patient.id  # 添加患者ID
        )
        # 计算同一个 letter_id 对应的润色记录数量
        count_list = db.session.query(PolishHistory.letter_id, db.func.count(PolishHistory.id)).group_by(PolishHistory.letter_id).all()
        count_dict = {letter_id: count for letter_id, count in count_list}
        count = int(count_dict[letter.id])
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!: {count}")
        
        return jsonify({
            'status': 'success',
            'polish_id': polish_history.id,
            'letter_id': letter.id,
            'patient_id': patient.id,  # 返回患者ID
            'polished_text': polished_text,
            'count': count
        })
        
    except Exception as e:
        print("润色失败:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/adopt_polish', methods=['POST'])
def adopt_polish():
    try:
        data = request.json
        
        # 获取感谢信记录以获取患者ID
        letter = Letter.query.get(data['letter_id'])
        if not letter:
            return jsonify({
                'status': 'error',
                'message': '未找到对应的感谢信记录'
            }), 404
            
        # 创建新的采纳记录，包含患者ID
        adoption = AdoptedPolish(
            letter_id=data['letter_id'],
            polish_id=data['polish_id'],
            patient_id=letter.patient_id
        )
        db.session.add(adoption)
        db.session.commit()
        
        return jsonify({
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/update_polish', methods=['POST'])
def update_polish():
    try:
        data = request.json
        print("接收到的更新请求:", data)  # 调试信息
        
        # 获取要更新的润色记录
        polish_history = PolishHistory.query.get(data['polish_id'])
        
        if polish_history:
            # 更新润色文本
            polish_history.polished_text = data['edited_text']
            db.session.commit()
            print(f"成功更新润色记录 ID: {polish_history.id}")  # 调试信息
            
            # 记录编辑保存行为
            record_user_action(
                data=data,
                action_type='click_save',
                polish_id=polish_history.id,
                letter_id=polish_history.letter_id
            )
            
            return jsonify({
                'status': 'success',
                'message': '更新成功'
            })
        else:
            print(f"未找到润色记录 ID: {data['polish_id']}")  # 调试信息
            return jsonify({
                'status': 'error',
                'message': '未找到对应的润色记录'
            }), 404
            
    except Exception as e:
        print("更新失败:", str(e))  # 调试信息
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/view_data')
@require_admin
def view_data():
    patients = Patient.query.all()
    letters = Letter.query.all()
    polish_history = PolishHistory.query.all()
    adopted_polish = AdoptedPolish.query.all()
    user_actions = UserAction.query.order_by(UserAction.created_at.desc()).all()
    
    return render_template('view_data.html', 
                         patients=patients,
                         letters=letters,
                         polish_history=polish_history,
                         adopted_polish=adopted_polish,
                         user_actions=user_actions,
                         Letter=Letter)

@app.route('/export_data')
@require_admin
def export_data():
    try:
        # 创建一个Excel写入器
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 导出患者信息
            patients_df = pd.DataFrame([{
                'id': p.id,
                'patient_name': p.patient_name,
                'gender': p.gender,
                'age': p.age,
                'disease': p.disease,
                'created_at': p.created_at
            } for p in Patient.query.all()])
            if not patients_df.empty:
                patients_df.to_excel(writer, sheet_name='Patients', index=False)
            
            # 导出感谢信数据
            letters_df = pd.DataFrame([{
                'id': l.id,
                'patient_id': l.patient_id,
                'patient_name': l.patient_name,
                'gender': l.gender,
                'age': l.age,
                'disease': l.disease,
                'doctor_name': l.doctor_name,
                'doctor_title': l.doctor_title,
                'doctor_department': l.doctor_department,
                'doctor_gender': l.doctor_gender,
                'hospital': l.hospital,
                'original_text': l.original_text,
                'created_at': l.created_at
            } for l in Letter.query.all()])
            if not letters_df.empty:
                letters_df.to_excel(writer, sheet_name='Letters', index=False)
            
            # 导出润色历史
            polish_df = pd.DataFrame([{
                'id': p.id,
                'letter_id': p.letter_id,
                'previous_text': p.previous_text,
                'polished_text': p.polished_text,
                'polish_options': p.polish_options,
                'created_at': p.created_at
            } for p in PolishHistory.query.all()])
            if not polish_df.empty:
                polish_df.to_excel(writer, sheet_name='Polish_History', index=False)
            
            # 导出采纳记录
            adopted_df = pd.DataFrame([{
                'id': a.id,
                'patient_id': a.patient_id,
                'letter_id': a.letter_id,
                'polish_id': a.polish_id,
                'created_at': a.created_at
            } for a in AdoptedPolish.query.all()])
            if not adopted_df.empty:
                adopted_df.to_excel(writer, sheet_name='Adopted_Polish', index=False)
            
            # 导出用户行为记录
            actions_df = pd.DataFrame([{
                'id': a.id,
                'patient_id': a.patient_id,
                'patient_name': a.patient_name,
                'gender': a.gender,
                'age': a.age,
                'disease': a.disease,
                'action_type': a.action_type,
                'action_detail': a.action_detail,
                'letter_id': a.letter_id,
                'polish_id': a.polish_id,
                'created_at': a.created_at
            } for a in UserAction.query.all()])
            if not actions_df.empty:
                actions_df.to_excel(writer, sheet_name='User_Actions', index=False)
            
            # 确保至少有一个工作表
            if all(df.empty for df in [patients_df, letters_df, polish_df, adopted_df, actions_df]):
                pd.DataFrame({'message': ['No data available']}).to_excel(writer, sheet_name='No_Data', index=False)
        
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'thankyou_letters_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        print(f"导出数据失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'导出数据失败: {str(e)}'
        }), 500

@app.route('/record_action', methods=['POST'])
def record_action():
    try:
        data = request.json
        action_type = data.get('action_type')
        polish_id = data.get('polish_id')
        action_detail = data.get('action_detail')

        # 通过 polish_id 获取相关信息
        polish_history = PolishHistory.query.get(polish_id)
        if polish_history:
            letter = Letter.query.get(polish_history.letter_id)
            if letter:
                # 记录用户行为
                user_action = UserAction(
                    patient_id=letter.patient_id,
                    patient_name=letter.patient_name,
                    gender=letter.gender,
                    age=letter.age,
                    disease=letter.disease,
                    action_type=action_type,
                    action_detail=action_detail,
                    letter_id=letter.id,
                    polish_id=polish_id
                )
                db.session.add(user_action)
                db.session.commit()
                
                return jsonify({'status': 'success'})
            
        return jsonify({'status': 'error', 'message': '未找到相关记录'}), 404
        
    except Exception as e:
        print(f"记录用户行为失败: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 管理页面路由
@app.route('/admin')
def admin():
    token = request.args.get('token')
    if token != ADMIN_TOKEN:
        return "未授权访问", 403
    return render_template('admin.html', admin_token=ADMIN_TOKEN)

@app.route('/copy_success')
def copy_success():
    return render_template('copy_success.html')

if __name__ == '__main__':
    with app.app_context():
        # 只在数据库不存在时创建表
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)
