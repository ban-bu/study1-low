# 导入所有必要的基础依赖
import streamlit as st
import warnings
warnings.filterwarnings('ignore')

from PIL import Image, ImageDraw
import requests
from io import BytesIO

# 处理可选依赖 - 移除直接导入cairosvg
# 设置标志变量来跟踪哪些库可用
CAIROSVG_AVAILABLE = False
SVGLIB_AVAILABLE = False

try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except (ImportError, OSError) as e:
    # 如果是系统级缺少依赖而不仅仅是库未安装
    st.warning("cairosvg库无法加载，尝试使用备选SVG处理方法。错误信息: " + str(e))
    # 尝试加载备选库
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPM
        SVGLIB_AVAILABLE = True
    except ImportError:
        st.warning("SVG处理库未安装或加载失败，SVG格式转换功能将不可用。将尝试直接处理图像。")

import base64
import numpy as np
import os
import pandas as pd
import uuid
import datetime
import json
import re

# Requires installation: pip install streamlit-image-coordinates
try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    from streamlit.components.v1 import html
    from streamlit_drawable_canvas import st_canvas
    INTERACTIVE_COMPONENTS_AVAILABLE = True
except ImportError:
    st.warning("交互组件库(streamlit-image-coordinates/streamlit-drawable-canvas)未安装，一些交互功能将不可用")
    INTERACTIVE_COMPONENTS_AVAILABLE = False

# 导入OpenAI配置
from openai import OpenAI
API_KEY = "sk-lNVAREVHjj386FDCd9McOL7k66DZCUkTp6IbV0u9970qqdlg"
BASE_URL = "https://api.deepbricks.ai/v1/"
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 导入面料纹理模块
from fabric_texture import apply_fabric_texture

# 导入SVG处理功能
from svg_utils import convert_svg_to_png

# Page configuration
st.set_page_config(
    page_title="AI Co-Creation - Low Recommendation Level",
    page_icon="👕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styles
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        height: 3rem;
        font-size: 1.2rem;
        font-weight: bold;
    }
    .design-area {
        border: 2px dashed #f63366;
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 20px;
    }
    .highlight-text {
        color: #f63366;
        font-weight: bold;
    }
    .purchase-intent {
        background-color: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
    }
    .rating-container {
        display: flex;
        justify-content: space-between;
        margin: 20px 0;
    }
    .design-gallery {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 10px;
        margin: 20px 0;
    }
    .design-item {
        border: 2px solid transparent;
        border-radius: 5px;
        transition: border-color 0.2s;
        cursor: pointer;
    }
    .design-item.selected {
        border-color: #f63366;
    }
    .movable-box {
        cursor: move;
    }
</style>
""", unsafe_allow_html=True)

# 数据文件路径 - 共享常量
DATA_FILE = "experiment_data.csv"

# Initialize session state
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())
if 'start_time' not in st.session_state:
    st.session_state.start_time = datetime.datetime.now()
if 'experiment_group' not in st.session_state:
    st.session_state.experiment_group = "Low Recommendation Level"
if 'base_image' not in st.session_state:
    st.session_state.base_image = None
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'final_design' not in st.session_state:
    st.session_state.final_design = None
if 'submitted' not in st.session_state:
    st.session_state.submitted = False
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'user_prompt' not in st.session_state:
    st.session_state.user_prompt = ""
if 'design_info' not in st.session_state:
    st.session_state.design_info = None
if 'is_generating' not in st.session_state:
    st.session_state.is_generating = False
if 'should_generate' not in st.session_state:
    st.session_state.should_generate = False
if 'generated_designs' not in st.session_state:
    st.session_state.generated_designs = []
if 'selected_design_index' not in st.session_state:
    st.session_state.selected_design_index = 0
if 'original_tshirt' not in st.session_state:
    # 加载原始白色T恤图像
    try:
        original_image_path = "white_shirt.png"
        possible_paths = [
            "white_shirt.png",
            "./white_shirt.png",
            "../white_shirt.png",
            "images/white_shirt.png",
        ]
        
        found = False
        for path in possible_paths:
            if os.path.exists(path):
                original_image_path = path
                found = True
                break
        
        if found:
            st.session_state.original_tshirt = Image.open(original_image_path).convert("RGBA")
        else:
            st.error("Could not find base T-shirt image")
            st.session_state.original_tshirt = None
    except Exception as e:
        st.error(f"Error loading T-shirt image: {str(e)}")
        st.session_state.original_tshirt = None

# 辅助函数
def get_ai_design_suggestions(user_preferences=None):
    """Get design suggestions from GPT-4o-mini with more personalized features"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    
    # Default prompt if no user preferences provided
    if not user_preferences:
        user_preferences = "casual fashion t-shirt design"
    
    # Construct the prompt
    prompt = f"""
    As a T-shirt design consultant, please provide personalized design suggestions for a "{user_preferences}" style T-shirt.
    
    Please provide the following design suggestions in JSON format:

    1. Color: Select the most suitable color for this style (provide name and hex code)
    2. Fabric: Select the most suitable fabric type (Cotton, Polyester, Cotton-Polyester Blend, Jersey, Linen, or Bamboo)
    3. Text: A suitable phrase or slogan that matches the style (keep it concise and impactful)
    4. Logo: A brief description of a logo/graphic element that would complement the design

    Return your response as a valid JSON object with the following structure:
    {{
        "color": {{
            "name": "Color name",
            "hex": "#XXXXXX"
        }},
        "fabric": "Fabric type",
        "text": "Suggested text or slogan",
        "logo": "Logo/graphic description"
    }}
    """
    
    try:
        # 调用GPT-4o-mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional T-shirt design consultant. Provide design suggestions in JSON format exactly as requested."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # 返回建议内容
        if response.choices and len(response.choices) > 0:
            suggestion_text = response.choices[0].message.content
            
            # 尝试解析JSON
            try:
                # 查找JSON格式的内容
                json_match = re.search(r'```json\s*(.*?)\s*```', suggestion_text, re.DOTALL)
                if json_match:
                    suggestion_json = json.loads(json_match.group(1))
                else:
                    # 尝试直接解析整个内容
                    suggestion_json = json.loads(suggestion_text)
                
                return suggestion_json
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                return {"error": f"Failed to parse design suggestions: {str(e)}"}
        else:
            return {"error": "Failed to get AI design suggestions. Please try again later."}
    except Exception as e:
        return {"error": f"Error getting AI design suggestions: {str(e)}"}

def generate_vector_image(prompt):
    """Generate an image based on the prompt"""
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            quality="standard"
        )
    except Exception as e:
        st.error(f"Error calling API: {e}")
        return None

    if resp and len(resp.data) > 0 and resp.data[0].url:
        image_url = resp.data[0].url
        try:
            image_resp = requests.get(image_url)
            if image_resp.status_code == 200:
                content_type = image_resp.headers.get("Content-Type", "")
                if "svg" in content_type.lower():
                    # 使用集中的SVG处理函数
                    return convert_svg_to_png(image_resp.content)
                else:
                    return Image.open(BytesIO(image_resp.content)).convert("RGBA")
            else:
                st.error(f"Failed to download image, status code: {image_resp.status_code}")
        except Exception as download_err:
            st.error(f"Error requesting image: {download_err}")
    else:
        st.error("Could not get image URL from API response.")
    return None

def change_shirt_color(image, color_hex, apply_texture=False, fabric_type=None):
    """Change T-shirt color with optional fabric texture"""
    # 转换十六进制颜色为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    
    # 创建副本避免修改原图
    colored_image = image.copy().convert("RGBA")
    
    # 获取图像数据
    data = colored_image.getdata()
    
    # 创建新数据
    new_data = []
    # 白色阈值 - 调整这个值可以控制哪些像素被视为白色/浅色并被改变
    threshold = 200
    
    for item in data:
        # 判断是否是白色/浅色区域 (RGB值都很高)
        if item[0] > threshold and item[1] > threshold and item[2] > threshold and item[3] > 0:
            # 保持原透明度，改变颜色
            new_color = (color_rgb[0], color_rgb[1], color_rgb[2], item[3])
            new_data.append(new_color)
        else:
            # 保持其他颜色不变
            new_data.append(item)
    
    # 更新图像数据
    colored_image.putdata(new_data)
    
    # 如果需要应用纹理
    if apply_texture and fabric_type:
        return apply_fabric_texture(colored_image, fabric_type)
    
    return colored_image

def apply_text_to_shirt(image, text, color_hex="#FFFFFF", font_size=80):
    """Apply text to T-shirt image"""
    if not text:
        return image
    
    # 创建副本避免修改原图
    result_image = image.copy().convert("RGBA")
    img_width, img_height = result_image.size
    
    # 创建透明的文本图层
    text_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    
    # 尝试加载字体
    from PIL import ImageFont
    import platform
    
    font = None
    try:
        system = platform.system()
        
        # 根据不同系统尝试不同的字体路径
        if system == 'Windows':
            font_paths = [
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/ARIAL.TTF",
                "C:/Windows/Fonts/calibri.ttf",
            ]
        elif system == 'Darwin':  # macOS
            font_paths = [
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ]
        else:  # Linux或其他
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            ]
        
        # 尝试加载每个字体
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                break
    except Exception as e:
        print(f"Error loading font: {e}")
    
    # 如果加载失败，使用默认字体
    if font is None:
        try:
            font = ImageFont.load_default()
        except:
            print("Could not load default font")
            return result_image
    
    # 将十六进制颜色转换为RGB
    color_rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    text_color = color_rgb + (255,)  # 添加不透明度
    
    # 计算文本位置 (居中)
    text_bbox = text_draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    text_x = (img_width - text_width) // 2
    text_y = (img_height // 3) - (text_height // 2)  # 放在T恤上部位置
    
    # 绘制文本
    text_draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    # 组合图像
    result_image = Image.alpha_composite(result_image, text_layer)
    
    return result_image

def apply_logo_to_shirt(shirt_image, logo_image, position="center", size_percent=30):
    """Apply logo to T-shirt image with positioning and sizing"""
    # 创建副本避免修改原图
    result_image = shirt_image.copy().convert("RGBA")
    logo = logo_image.copy().convert("RGBA")
    
    # 根据百分比调整logo大小
    shirt_width, shirt_height = result_image.size
    target_width = int(shirt_width * (size_percent / 100))
    
    # 保持纵横比
    logo_width, logo_height = logo.size
    ratio = logo_width / logo_height
    target_height = int(target_width / ratio)
    
    # 调整logo大小
    logo = logo.resize((target_width, target_height), Image.LANCZOS)
    
    # 计算位置
    if position == "center":
        paste_x = (shirt_width - target_width) // 2
        paste_y = (shirt_height - target_height) // 2
    elif position == "chest":
        paste_x = (shirt_width - target_width) // 2
        paste_y = shirt_height // 3 - target_height // 2
    elif position == "bottom":
        paste_x = (shirt_width - target_width) // 2
        paste_y = 2 * shirt_height // 3 - target_height // 2
    elif position == "pocket":
        paste_x = shirt_width // 4 - target_width // 2
        paste_y = shirt_height // 3 - target_height // 2
    elif position == "back":
        paste_x = (shirt_width - target_width) // 2
        paste_y = shirt_height // 4 - target_height // 2
    else:
        # 默认中心位置
        paste_x = (shirt_width - target_width) // 2
        paste_y = (shirt_height - target_height) // 2
    
    # 粘贴logo到衬衫
    result_image.paste(logo, (paste_x, paste_y), logo)
    
    return result_image

def generate_complete_design(design_prompt, variation_id=None):
    """Generate complete T-shirt design from user prompt"""
    import re
    
    # 保存一个唯一ID标识此次生成，用于后期识别和追踪
    if variation_id is None:
        variation_id = str(uuid.uuid4())[:8]
    
    # 步骤1: 获取AI生成的设计建议
    design_suggestions = get_ai_design_suggestions(design_prompt)
    
    if "error" in design_suggestions:
        return None, f"Error getting design suggestions: {design_suggestions['error']}", variation_id
    
    # 提取设计元素
    try:
        color_name = design_suggestions.get("color", {}).get("name", "Blue")
        color_hex = design_suggestions.get("color", {}).get("hex", "#3b82f6")
        if not color_hex.startswith("#"):
            color_hex = "#" + color_hex
        
        fabric_type = design_suggestions.get("fabric", "Cotton")
        text = design_suggestions.get("text", "")
        logo_desc = design_suggestions.get("logo", "A simple minimalist logo")
    except Exception as e:
        print(f"Error extracting design elements: {e}")
        color_name = "Blue"
        color_hex = "#3b82f6"
        fabric_type = "Cotton"
        text = ""
        logo_desc = "A simple minimalist logo"
    
    # 步骤2: 创建完整的logo生成提示词
    logo_prompt = f"""
    Design a high-quality, professional logo for a T-shirt with these requirements:
    - Logo content: {logo_desc}
    - Style: Clean, modern, suitable for a T-shirt print
    - Make the logo transparent background (PNG)
    - Avoid text in the logo
    - Simple but professional looking
    - Variation ID: {variation_id}
    """
    
    # 步骤3: 生成logo图像
    logo_image = generate_vector_image(logo_prompt)
    
    if logo_image is None:
        return None, "Error generating logo image", variation_id
    
    # 步骤4: 将设计应用到T恤上
    if st.session_state.original_tshirt is None:
        return None, "Original T-shirt template is missing", variation_id
    
    # 步骤4.1: 改变T恤颜色
    colored_shirt = change_shirt_color(
        st.session_state.original_tshirt, 
        color_hex,
        apply_texture=st.session_state.get("apply_texture", False),
        fabric_type=fabric_type.lower() if fabric_type else None
    )
    
    # 步骤4.2: 添加logo
    shirt_with_logo = apply_logo_to_shirt(
        colored_shirt,
        logo_image,
        position="chest",
        size_percent=30
    )
    
    # 步骤4.3: 添加文本
    final_design = apply_text_to_shirt(
        shirt_with_logo,
        text,
        color_hex="#FFFFFF" if sum(int(color_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) < 380 else "#000000",
        font_size=60
    )
    
    # 步骤5: 创建设计信息记录
    design_info = {
        "prompt": design_prompt,
        "color": {"name": color_name, "hex": color_hex},
        "fabric": fabric_type,
        "text": text,
        "logo": logo_desc,
        "variation_id": variation_id,
        "created_at": datetime.datetime.now().isoformat()
    }
    
    return final_design, design_info, variation_id

def generate_single_design(design_prompt, variation_id=None):
    """生成单个设计"""
    try:
        final_design, design_info, variation_id = generate_complete_design(design_prompt, variation_id)
        if final_design:
            return final_design, design_info
        return None, f"Generation failed: {design_info}"
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return None, f"Error: {str(e)}\n{error_details}"

# 主应用函数
def main():
    # 页面标题和介绍
    st.title("👕 AI T恤设计助手 - 低级推荐")
    st.markdown("### 使用AI设计您专属的T恤")
    
    # 创建两列布局
    design_col, input_col = st.columns([3, 2])
    
    with design_col:
        # 创建占位区域用于T恤设计展示
        design_area = st.empty()
        
        # 在设计区域显示当前状态的T恤设计
        if st.session_state.final_design is not None:
            with design_area.container():
                st.markdown("### 您的定制T恤设计")
                st.image(st.session_state.final_design, use_container_width=True)
        elif len(st.session_state.generated_designs) > 0:
            with design_area.container():
                st.markdown("### 生成的设计选项")
                design, _ = st.session_state.generated_designs[0]
                st.image(design, use_container_width=True)
                
                # 添加确认选择按钮
                if st.button("✅ 确认选择"):
                    selected_design, selected_info = st.session_state.generated_designs[0]
                    st.session_state.final_design = selected_design
                    st.session_state.design_info = selected_info
                    st.session_state.generated_designs = []  # 清空生成的设计列表
                    st.rerun()
        else:
            # 显示原始空白T恤
            with design_area.container():
                st.markdown("### T恤设计预览")
                if st.session_state.original_tshirt is not None:
                    st.image(st.session_state.original_tshirt, use_container_width=True)
                else:
                    st.info("无法加载原始T恤图像，请刷新页面")
    
    with input_col:
        # 设计提示词和选项区
        st.markdown("### 设计选项")
        
        # 添加简短说明
        st.markdown("""
        <div style="margin-bottom: 15px; padding: 10px; background-color: #f0f2f6; border-radius: 5px;">
        <p style="margin: 0; font-size: 14px;">输入三个关键词来描述您理想的T恤设计。
        我们的AI将结合这些特点为您创建独特的设计。</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 三个关键词输入框
        keyword_cols = st.columns(3)
        
        # 初始化关键词状态
        if 'keyword1' not in st.session_state:
            st.session_state.keyword1 = ""
        if 'keyword2' not in st.session_state:
            st.session_state.keyword2 = ""
        if 'keyword3' not in st.session_state:
            st.session_state.keyword3 = ""
        
        # 更新关键词的函数
        def update_keyword1():
            st.session_state.keyword1 = st.session_state.keyword1_input
            
        def update_keyword2():
            st.session_state.keyword2 = st.session_state.keyword2_input
            
        def update_keyword3():
            st.session_state.keyword3 = st.session_state.keyword3_input
        
        # 显示关键词输入框
        with keyword_cols[0]:
            st.text_input("关键词 1", key="keyword1_input", 
                        value=st.session_state.keyword1, 
                        on_change=update_keyword1,
                        placeholder="例如: 简约")
            
        with keyword_cols[1]:
            st.text_input("关键词 2", key="keyword2_input", 
                        value=st.session_state.keyword2, 
                        on_change=update_keyword2,
                        placeholder="例如: 蓝色")
            
        with keyword_cols[2]:
            st.text_input("关键词 3", key="keyword3_input", 
                        value=st.session_state.keyword3, 
                        on_change=update_keyword3,
                        placeholder="例如: 海洋")
        
        # 组合关键词
        combined_keywords = " ".join(filter(None, [
            st.session_state.keyword1, 
            st.session_state.keyword2, 
            st.session_state.keyword3
        ]))
        
        # 生成按钮
        generate_btn = st.button("🎨 生成T恤设计", type="primary", use_container_width=True)
        
        if generate_btn:
            if not combined_keywords:
                st.error("请至少输入一个关键词来描述您想要的T恤设计。")
            else:
                # 设置生成标志
                st.session_state.should_generate = True
                st.session_state.user_prompt = combined_keywords
        
        # 重置按钮
        reset_col1, reset_col2 = st.columns(2)
        with reset_col1:
            if st.button("🔄 重置设计", use_container_width=True):
                # 重置设计相关状态
                st.session_state.final_design = None
                st.session_state.generated_designs = []
                st.session_state.design_info = None
                st.rerun()
        
        with reset_col2:
            if st.button("🗑️ 清除关键词", use_container_width=True):
                # 清除关键词
                st.session_state.keyword1 = ""
                st.session_state.keyword2 = ""
                st.session_state.keyword3 = ""
                st.rerun()
        
        # 生成设计
        if st.session_state.should_generate:
            with st.spinner("AI正在为您生成T恤设计..."):
                try:
                    st.session_state.is_generating = True
                    
                    # 使用关键词生成设计
                    final_design, design_info = generate_single_design(st.session_state.user_prompt)
                    
                    if final_design and isinstance(final_design, Image.Image):
                        # 保存生成的设计
                        st.session_state.generated_designs = [(final_design, design_info)]
                    else:
                        st.error(f"生成设计失败: {design_info}")
                except Exception as e:
                    st.error(f"生成过程中出错: {str(e)}")
                finally:
                    st.session_state.is_generating = False
                    st.session_state.should_generate = False
                    st.rerun()
        
        # 显示当前设计信息
        if st.session_state.design_info and st.session_state.final_design is not None:
            st.markdown("### 当前设计详情")
            info = st.session_state.design_info
            
            # 创建表格显示设计详情
            info_df = pd.DataFrame({
                "属性": ["颜色", "面料", "文本", "图案描述"],
                "值": [
                    f"{info.get('color', {}).get('name', 'N/A')} ({info.get('color', {}).get('hex', '#000000')})",
                    info.get("fabric", "N/A"),
                    info.get("text", "N/A"),
                    info.get("logo", "N/A")
                ]
            })
            
            st.dataframe(info_df, hide_index=True, use_container_width=True)

# 运行应用
if __name__ == "__main__":
    main() 
