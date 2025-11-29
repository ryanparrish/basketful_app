document.addEventListener('DOMContentLoaded', function () {
    const imageInput = document.getElementById('id_image');  // Change if your field name is different

    if (!imageInput) return;

    const preview = document.createElement('img');
    preview.style.maxHeight = '200px';
    preview.style.marginTop = '10px';

    imageInput.parentNode.appendChild(preview);

    imageInput.addEventListener('change', function () {
        const file = this.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function (e) {
                preview.src = e.target.result;
            };
            reader.readAsDataURL(file);
        } else {
            preview.src = '';
        }
    });
});
