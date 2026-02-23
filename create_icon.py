from PIL import Image, ImageDraw

def create_image():
    # 64x64 크기의 투명 배경 이미지 생성
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    
    # 둥근 사각형 그리기 (파란색)
    dc.rounded_rectangle((5, 5, 59, 59), radius=15, fill=(0, 122, 204), outline=(255, 255, 255), width=3)
    
    # 가운데 'L' 문자 그리기 (흰색)
    dc.text((22, 16), "L", fill=(255, 255, 255), font_size=30)
    
    # 저장
    image.save('icon.png')
    print("icon.png 파일이 생성되었습니다.")

if __name__ == '__main__':
    create_image()
