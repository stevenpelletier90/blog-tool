from blog_extractor import BlogExtractor
import re

extractor = BlogExtractor(verbose=False)
data = extractor.extract_blog_data('https://www.blog.kirkbrotherschevroletofvicksburg.com/post/mastering-vehicle-negotiation-strategies-pro-tips-from-kirk-brothers-chevrolet-of-vicksburg')

# Find all image src URLs
images = re.findall(r'<img[^>]+src="([^"]+)"', data.get('content', ''))

print(f'=== FOUND {len(images)} IMAGES ===\n')
for i, img_url in enumerate(images, 1):
    # Check if it's full quality (should have larger dimensions like w_1000)
    # or low quality (smaller dimensions like w_137)
    if 'w_' in img_url:
        width = re.search(r'w_(\d+)', img_url)
        if width:
            print(f'{i}. Width: {width.group(1)}px - {img_url[:80]}...')
    else:
        print(f'{i}. {img_url[:80]}...')
