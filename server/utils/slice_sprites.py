import matplotlib.pyplot as plt
import numpy as np
import os

def slice_sprites():
    src = r"c:\Users\USER\Desktop\IOT_REPO_BRAIN_MUSIC_RESEARCH-1\server\assets\sonic_sheet.png"
    out_dir = r"c:\Users\USER\Desktop\IOT_REPO_BRAIN_MUSIC_RESEARCH-1\server\assets"
    
    if not os.path.exists(src):
        print("Source file not found!")
        return

    # DEBUG: Check header
    with open(src, 'rb') as f:
        header = f.read(16)
        print(f"File header bytes: {header}")

    # Load image (H, W, 4) or (H, W, 3)
    try:
        img = plt.imread(src)
    except Exception as e:
        print(f"Matplotlib load failed: {e}")
        # Try PIL directly
        from PIL import Image
        pil_img = Image.open(src)
        print(f"PIL detected format: {pil_img.format}")
        img = np.array(pil_img)
        # Scale to 0-1 if int
        if img.dtype == np.uint8:
            img = img.astype(float) / 255.0

    # CROP HEADER (Remove text at top)
    # Assume top 60 pixels is text
    img = img[60:, :, :]
            
    # Add Alpha Channel if missing
    if img.shape[2] == 3:
        # Create alpha channel based on "Not White"
        # White is (1,1,1). Allow tolerance.
        dist_from_white = np.sqrt(np.sum((img - 1.0)**2, axis=2))
        alpha = np.where(dist_from_white < 0.2, 0.0, 1.0)
        img = np.dstack((img, alpha))
    
    H, W, C = img.shape
    
    # Check if we have alpha channel
    has_alpha = img.shape[2] == 4
    
    # Calculate column sums to find content vs whitespace
    # If alpha: check alpha > 0. If no alpha: check not-white (approx)
    
    H, W, C = img.shape
    print(f"Image shape: {H}x{W}x{C}")
    
    # Create mask of "content"
    if has_alpha:
        # Alpha channel > 0.1
        mask = img[:, :, 3] > 0.1
    else:
        # Assume white background (1,1,1) is empty
        # Distance from white > 0.1
        # Simple: sum of RGB < 2.9 (since white is 1,1,1 or 255,255,255)
        # Matplotlib Imread returns 0-1 floats usually for PNG
        mask = np.sum(img[:, :, :3], axis=2) < 2.95
        
    # Project to X axis (columns)
    col_has_content = np.any(mask, axis=0)
    
    # Find active regions
    # "islands" of True
    frames = []
    start = -1
    for x in range(W):
        if col_has_content[x]:
            if start == -1: start = x
        else:
            if start != -1:
                # End of a region
                frames.append((start, x))
                start = -1
    
    if start != -1:
        frames.append((start, W))
        
    # Filter small frames (noise)
    frames = [f for f in frames if (f[1] - f[0]) > 50]
        
    print(f"Found {len(frames)} valid frames: {frames}")
    
    # Save individual frames
    # Ideally standardizing size, but let's just save crops first
    # And crop Y too?
    
    # Global Y bounds
    row_has_content = np.any(mask, axis=1)
    # Find min/max Y with content
    y_indices = np.where(row_has_content)[0]
    if len(y_indices) > 0:
        y_min, y_max = y_indices[0], y_indices[-1]
    else:
        y_min, y_max = 0, H

    # Pad Y slightly
    y_min = max(0, y_min - 5)
    y_max = min(H, y_max + 5)

    for i, (x1, x2) in enumerate(frames):
        # Pad X
        x1 = max(0, x1 - 5)
        x2 = min(W, x2 + 5)
        
        crop = img[y_min:y_max, x1:x2, :]
        
        fname = os.path.join(out_dir, f"sonic_run_{i}.png")
        plt.imsave(fname, crop)
        print(f"Saved {fname}")

if __name__ == "__main__":
    slice_sprites()
