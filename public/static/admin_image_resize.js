// Shrinks menu photos in the browser before they are uploaded.
// Phone photos can be 5+ MB; a 1000px JPEG is ~100-200 KB and looks the same on the menu.

const MAX_IMAGE_SIDE = 1000;
const JPEG_QUALITY = 0.85;

const shrinkImage = (file) => new Promise((resolve) => {
    const image = new Image();
    image.onload = () => {
        const scale = Math.min(1, MAX_IMAGE_SIDE / Math.max(image.width, image.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(image.width * scale);
        canvas.height = Math.round(image.height * scale);
        const context = canvas.getContext('2d');
        context.fillStyle = '#fff'; // transparent PNG areas become white instead of black
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        URL.revokeObjectURL(image.src);
        canvas.toBlob((blob) => resolve(blob), 'image/jpeg', JPEG_QUALITY);
    };
    image.onerror = () => resolve(null);
    image.src = URL.createObjectURL(file);
});

document.querySelectorAll('input[type="file"][name="image"]').forEach((input) => {
    input.addEventListener('change', async () => {
        const file = input.files[0];
        if (!file) {
            return;
        }
        const blob = await shrinkImage(file);
        if (!blob || blob.size >= file.size) {
            return; // keep the original if shrinking didn't help
        }
        const smallerName = file.name.replace(/\.[^.]+$/, '') + '.jpg';
        const transfer = new DataTransfer();
        transfer.items.add(new File([blob], smallerName, { type: 'image/jpeg' }));
        input.files = transfer.files;
    });
});
