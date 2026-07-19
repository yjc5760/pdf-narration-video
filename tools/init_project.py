import sys
import os
from pathlib import Path
import subprocess

def main():
    if len(sys.argv) < 2:
        print("用法: init_project.bat <PDF檔案路徑>")
        sys.exit(1)
        
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"[錯誤] 找不到檔案: {pdf_path}")
        sys.exit(1)
        
    project_name = pdf_path.stem
    project_dir = Path(project_name)
    images_dir = project_dir / "images"
    
    if project_dir.exists():
        print(f"[警告] 專案資料夾 '{project_name}' 已經存在！")
        sys.exit(1)
        
    print(f"建立專案資料夾: {project_name}")
    images_dir.mkdir(parents=True, exist_ok=True)
    
    print("正在將 PDF 轉換為圖片 (pdftoppm)...")
    try:
        subprocess.run(["pdftoppm", "-jpeg", "-r", "150", str(pdf_path), str(images_dir / "slide")], check=True)
    except FileNotFoundError:
        print("[錯誤] 找不到 pdftoppm 指令。請確認 Poppler 已安裝並加入環境變數 PATH 中。")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[錯誤] pdftoppm 執行失敗: {e}")
        sys.exit(1)
    
    images = list(images_dir.glob("slide-*.jpg"))
    image_count = len(images)
    print(f"共轉換出 {image_count} 張圖片。")
    
    narration_path = project_dir / "narration.md"
    print(f"正在產生講稿模板: {narration_path}")
    
    with open(narration_path, "w", encoding="utf-8") as f:
        f.write(f"# {project_name} 講稿\n\n")
        for i in range(1, image_count + 1):
            f.write(f"## 頁 {i} — 標題\n\n[請在此輸入講稿內容]\n\n")
            
    print("========================================")
    print(f"專案 {project_name} 初始化完成！")
    print("下一步：")
    print(f"1. 進入 {project_name} 資料夾，編輯 narration.md")
    print(f"2. 執行指令: ..\\tools\\run_azure.bat")
    print("========================================")

if __name__ == "__main__":
    main()
