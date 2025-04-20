"""
SVG处理工具 - 用于将SVG格式转换为PNG
"""
import io
from PIL import Image

def convert_svg_to_png(svg_content):
    """
    将SVG内容转换为PNG格式
    
    参数:
        svg_content: SVG内容（字节格式）
    
    返回:
        PIL.Image: 转换后的PNG图像
    """
    try:
        # 尝试使用cairosvg (如果已安装)
        import cairosvg
        png_data = cairosvg.svg2png(bytestring=svg_content)
        return Image.open(io.BytesIO(png_data))
    except ImportError:
        # 如果cairosvg未安装，尝试使用svglib
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPM
            import io
            
            drawing = svg2rlg(io.BytesIO(svg_content))
            png_data = renderPM.drawToString(drawing, fmt='PNG')
            return Image.open(io.BytesIO(png_data))
        except ImportError:
            # 如果两个库都未安装，返回错误信息
            raise ImportError("无法转换SVG，请安装cairosvg或svglib库。")
    except Exception as e:
        # 处理其他可能的错误
        raise Exception(f"SVG转换失败: {str(e)}") 