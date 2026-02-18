/**
 * Dropzone Custom Handler สำหรับ Django FormSet
 *
 * การใช้งาน:
 * 1. เพิ่ม CSS: <link rel="stylesheet" href="{% static 'dropzone-custom.css' %}">
 * 2. เพิ่ม JS: <script src="{% static 'dropzone-custom.js' %}"></script>
 * 3. เรียกใช้: initDropzoneFormset(options)
 *
 * ตัวอย่าง:
 * initDropzoneFormset({
 *     dropzoneId: 'dropzone-area',
 *     formsetContainerId: 'formset-container',
 *     formsetFormsId: 'formset-forms',
 *     previewContainerId: 'image-preview',
 *     formId: 'dog-form',
 *     maxFiles: 5,
 *     existingImagesCount: 0
 * });
 */

function initDropzoneFormset(options) {
  // ตั้งค่า default options
  const config = {
    dropzoneId: "dropzone-area",
    formsetContainerId: "formset-container",
    formsetFormsId: "formset-forms",
    previewContainerId: "image-preview",
    formId: null, // ถ้าไม่ระบุจะไม่เพิ่ม submit handler
    maxFiles: 5,
    existingImagesCount: 0,
    acceptedFiles: "image/*",
    ...options,
  };

  // ตรวจสอบว่า Dropzone โหลดแล้วหรือยัง
  if (typeof Dropzone === "undefined") {
    console.log("Waiting for Dropzone.js to load...");
    setTimeout(() => initDropzoneFormset(config), 100);
    return;
  }

  console.log("Dropzone.js loaded, initializing...");

  // ปิดการใช้งาน auto-discover ของ Dropzone
  Dropzone.autoDiscover = false;

  // ตรวจสอบว่า element มีอยู่จริง
  const dropzoneElement = document.getElementById(config.dropzoneId);
  if (!dropzoneElement) {
    console.error(`Dropzone element not found: #${config.dropzoneId}`);
    return;
  }

  // ตรวจสอบว่า element นี้มี Dropzone instance อยู่แล้วหรือไม่
  if (dropzoneElement.dropzone) {
    console.log("Dropzone already initialized, destroying old instance...");
    dropzoneElement.dropzone.destroy();
  }

  // เก็บไฟล์ที่อัพโหลด
  let uploadedFiles = [];

  // ฟังก์ชันสำหรับนับรูปเดิมที่ไม่ถูกลบ (dynamic)
  function getExistingImagesCount() {
    const deleteCheckboxesInDocument = document.querySelectorAll(
      '.existing-image-item input[type="checkbox"][name$="-DELETE"]:not(:checked)'
    );
    return deleteCheckboxesInDocument.length;
  }

  // สร้าง Dropzone instance
  let dropzone;
  try {
    dropzone = new Dropzone(`#${config.dropzoneId}`, {
      url: "#", // ไม่ใช้ auto-upload
      autoProcessQueue: false,
      addRemoveLinks: false,
      maxFiles: config.maxFiles,
      acceptedFiles: config.acceptedFiles,
      dictDefaultMessage: "",
      dictMaxFilesExceeded: `คุณสามารถอัพโหลดได้สูงสุด ${config.maxFiles} รูป`,
      clickable: true,
      init: function () {
        const dz = this;
        console.log("Dropzone initialized successfully");

        // เมื่อเพิ่มไฟล์
        dz.on("addedfile", function (file) {
          console.log("File added:", file.name);
          const existingCount = getExistingImagesCount();
          const totalFiles = uploadedFiles.length + existingCount;
          if (totalFiles >= config.maxFiles) {
            dz.removeFile(file);
            alert(`คุณสามารถอัพโหลดได้สูงสุด ${config.maxFiles} รูป`);
            return;
          }

          uploadedFiles.push(file);
          updateFormset();
          updatePreview();
        });

        // เมื่อลบไฟล์
        dz.on("removedfile", function (file) {
          console.log("File removed:", file.name);
          uploadedFiles = uploadedFiles.filter((f) => f !== file);
          updateFormset();
          updatePreview();
        });

        // เมื่อมี error
        dz.on("error", function (file, message) {
          console.error("Dropzone error:", message);
          alert("เกิดข้อผิดพลาด: " + message);
        });
      },
    });
    console.log("Dropzone instance created:", dropzone);
  } catch (error) {
    console.error("Error creating Dropzone:", error);
    alert("เกิดข้อผิดพลาดในการสร้าง Dropzone: " + error.message);
    return;
  }

  // อัพเดต FormSet
  function updateFormset() {
    const formsetContainer = document.getElementById(config.formsetContainerId);
    if (!formsetContainer) {
      console.error(
        `Formset container not found: #${config.formsetContainerId}`
      );
      return;
    }

    const formsetForms = document.getElementById(config.formsetFormsId);
    if (!formsetForms) {
      console.error(`Formset forms not found: #${config.formsetFormsId}`);
      return;
    }

    const managementForm = formsetContainer.querySelector(
      '[name$="-TOTAL_FORMS"]'
    );
    const initialForm = formsetContainer.querySelector(
      '[name$="-INITIAL_FORMS"]'
    );
    const minNumForm = formsetContainer.querySelector(
      '[name$="-MIN_NUM_FORMS"]'
    );
    const maxNumForm = formsetContainer.querySelector(
      '[name$="-MAX_NUM_FORMS"]'
    );

    // นับรูปเดิมที่ไม่ถูกลบ (dynamic)
    // const existingNotDeleted = getExistingImagesCount(); // ไม่ใช้แล้วสำหรับการคำนวณ index

    // ล้าง formset forms สำหรับรูปใหม่
    formsetForms.innerHTML = "";

    // ดึงค่า INITIAL_FORMS (จำนวนรูปที่มีอยู่ใน DB)
    // ค่านี้ไม่ควรถูกเปลี่ยนโดย JS เพราะ Django ใช้ตรวจสอบว่ามีรูปเดิมกี่รูป
    const initialFormsCount = initialForm ? parseInt(initialForm.value) : 0;

    // สร้าง form สำหรับแต่ละไฟล์ใหม่
    // เริ่มต้น index ต่อจากรูปเดิมทั้งหมด (ไม่ว่าจะถูกลบหรือไม่)
    uploadedFiles.forEach((file, index) => {
      const formIndex = initialFormsCount + index;
      const formDiv = document.createElement("div");
      formDiv.innerHTML = `
                <input type="file" name="images-${formIndex}-image" id="id_images-${formIndex}-image" style="display: none;">
            `;
      formsetForms.appendChild(formDiv);

      // ใส่ไฟล์เข้าไปใน input
      const fileInput = formDiv.querySelector('input[type="file"]');
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      fileInput.files = dataTransfer.files;
    });

    // อัพเดต TOTAL_FORMS
    // TOTAL_FORMS = จำนวนรูปเดิม (INITIAL_FORMS) + รูปใหม่ที่เพิ่มเข้ามา
    if (managementForm) {
      managementForm.value = initialFormsCount + uploadedFiles.length;
    }

    // ไม่ต้องอัพเดต INITIAL_FORMS เพราะค่านี้ต้องคงที่เพื่อให้ Django รู้ว่ามีรูปเดิมกี่รูป
    // if (initialForm) initialForm.value = existingNotDeleted;

    if (minNumForm) minNumForm.value = 0;
    if (maxNumForm) maxNumForm.value = config.maxFiles;
  }

  // อัพเดต Preview
  function updatePreview() {
    const previewContainer = document.getElementById(config.previewContainerId);
    if (!previewContainer) {
      console.error(
        `Preview container not found: #${config.previewContainerId}`
      );
      return;
    }

    previewContainer.innerHTML = "";

    if (uploadedFiles.length > 0) {
      const title = document.createElement("h3");
      title.className =
        "text-md font-semibold text-gray-700 mb-2 col-span-full";
      title.textContent = "รูปภาพใหม่:";
      previewContainer.appendChild(title);
    }

    uploadedFiles.forEach((file, index) => {
      const previewDiv = document.createElement("div");
      previewDiv.className = "relative";

      const img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      img.className = "w-full h-32 object-cover rounded-md border";
      img.alt = `Preview ${index + 1}`;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className =
        "absolute top-2 right-2 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center hover:bg-red-600";
      removeBtn.innerHTML = "×";
      removeBtn.onclick = function () {
        dropzone.removeFile(file);
      };

      previewDiv.appendChild(img);
      previewDiv.appendChild(removeBtn);
      previewContainer.appendChild(previewDiv);
    });
  }

  // เมื่อ submit form (ถ้าระบุ formId)
  if (config.formId) {
    const form = document.getElementById(config.formId);
    if (form) {
      form.addEventListener("submit", function (e) {
        // อัพเดต formset ก่อน submit
        updateFormset();
      });
    }
  }

  // ฟังก์ชันสำหรับจัดการการลบรูปเดิม
  function setupExistingImageRemoval() {
    // ใช้ event delegation เพื่อป้องกันการเพิ่ม event listener ซ้ำ
    const existingImagesContainer =
      document.querySelector("#existing-images") || document;

    // ลบ event listener เก่าถ้ามี (ถ้าเรียกใช้ซ้ำ)
    if (existingImagesContainer._dropzoneRemovalHandler) {
      existingImagesContainer.removeEventListener(
        "click",
        existingImagesContainer._dropzoneRemovalHandler
      );
    }

    // สร้าง event handler ใหม่
    existingImagesContainer._dropzoneRemovalHandler = function (e) {
      // ตรวจสอบว่าคลิกที่ปุ่มลบหรือไม่
      if (!e.target.closest(".remove-existing-image")) return;

      const btn = e.target.closest(".remove-existing-image");
      const imageItem = btn.closest(".existing-image-item");
      if (!imageItem) return;

      const deleteCheckbox = imageItem.querySelector(
        'input[type="checkbox"][name$="-DELETE"]'
      );
      if (deleteCheckbox && !deleteCheckbox.checked) {
        // Mark สำหรับลบ
        deleteCheckbox.checked = true;

        // เพิ่ม animation และ styling
        imageItem.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        imageItem.style.opacity = "0.5";
        imageItem.style.transform = "scale(0.95)";
        imageItem.style.pointerEvents = "none";

        // เพิ่ม overlay เพื่อแสดงว่าถูกลบแล้ว
        let overlay = imageItem.querySelector(".deletion-overlay");
        if (!overlay) {
          overlay = document.createElement("div");
          overlay.className =
            "deletion-overlay absolute inset-0 bg-black bg-opacity-50 rounded-md flex items-center justify-center z-10";
          overlay.innerHTML =
            '<span class="text-white font-bold text-lg">ถูกลบ</span>';
          imageItem.appendChild(overlay);
        }

        // อัพเดต formset
        updateFormset();
        updatePreview();

        console.log("Existing image marked for deletion");
      }
    };

    // เพิ่ม event listener
    existingImagesContainer.addEventListener(
      "click",
      existingImagesContainer._dropzoneRemovalHandler
    );
  }

  // เรียกใช้ setup เมื่อ initialize
  setupExistingImageRemoval();

  // เพิ่ม method updateFormset และ setupExistingImageRemoval ให้ dropzone instance
  dropzone.updateFormset = updateFormset;
  dropzone.setupExistingImageRemoval = setupExistingImageRemoval;
  dropzone.getExistingImagesCount = getExistingImagesCount;

  // Return dropzone instance สำหรับการใช้งานเพิ่มเติม
  return dropzone;
}

/**
 * Dropzone สำหรับอัปโหลดไฟล์เดี่ยว ให้ผูกกับ input file เดิม (เช่น Notification.image)
 *
 * ตัวอย่างการใช้งานใน template:
 * <input type="file" name="image" id="id_image" style="display:none;">
 * <div id="dropzone-area"></div>
 * <div id="image-preview"></div>
 *
 * <script>
 *   initDropzoneSingle({
 *     dropzoneId: 'dropzone-area',
 *     previewContainerId: 'image-preview',
 *     inputId: 'id_image',
 *     formId: 'notification-form',
 *     maxFiles: 1,
 *   });
 * </script>
 */
function initDropzoneSingle(options) {
  const config = {
    dropzoneId: "dropzone-area",
    previewContainerId: "image-preview",
    inputId: "id_image",
    formId: null,
    maxFiles: 1,
    acceptedFiles: "image/*",
    ...options,
  };

  if (typeof Dropzone === "undefined") {
    console.log("Waiting for Dropzone.js to load (single)...");
    setTimeout(() => initDropzoneSingle(config), 100);
    return;
  }

  Dropzone.autoDiscover = false;

  const dropzoneElement = document.getElementById(config.dropzoneId);
  if (!dropzoneElement) {
    console.error(`Dropzone element not found: #${config.dropzoneId}`);
    return;
  }

  const fileInput = document.getElementById(config.inputId);
  if (!fileInput) {
    console.error(`File input not found: #${config.inputId}`);
    return;
  }

  if (dropzoneElement.dropzone) {
    dropzoneElement.dropzone.destroy();
  }

  let currentFile = null;

  let dropzone;
  try {
    dropzone = new Dropzone(`#${config.dropzoneId}`, {
      url: "#",
      autoProcessQueue: false,
      addRemoveLinks: false,
      maxFiles: config.maxFiles,
      acceptedFiles: config.acceptedFiles,
      dictDefaultMessage: "",
      dictMaxFilesExceeded: "สามารถอัปโหลดได้เพียง 1 รูปภาพ",
      clickable: true,
      init: function () {
        const dz = this;

        dz.on("addedfile", function (file) {
          // จำกัดให้มีได้เพียงไฟล์เดียว
          if (currentFile) {
            dz.removeFile(currentFile);
          }
          currentFile = file;
          updateInput();
          updatePreview();
        });

        dz.on("removedfile", function (file) {
          if (file === currentFile) {
            currentFile = null;
            clearInput();
            updatePreview();
          }
        });

        dz.on("error", function (file, message) {
          console.error("Dropzone (single) error:", message);
          alert("เกิดข้อผิดพลาด: " + message);
        });
      },
    });
  } catch (error) {
    console.error("Error creating Dropzone (single):", error);
    alert("เกิดข้อผิดพลาดในการสร้าง Dropzone: " + error.message);
    return;
  }

  function updateInput() {
    if (!currentFile) return;
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(currentFile);
    fileInput.files = dataTransfer.files;
  }

  function clearInput() {
    fileInput.value = "";
  }

  function updatePreview() {
    const previewContainer = document.getElementById(config.previewContainerId);
    if (!previewContainer) {
      console.error(
        `Preview container not found: #${config.previewContainerId}`
      );
      return;
    }

    previewContainer.innerHTML = "";

    if (!currentFile) return;

    const previewDiv = document.createElement("div");
    previewDiv.className = "relative";

    const img = document.createElement("img");
    img.src = URL.createObjectURL(currentFile);
    img.className = "w-full h-32 object-cover rounded-md border";
    img.alt = "Preview";

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className =
      "absolute top-2 right-2 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center hover:bg-red-600";
    removeBtn.innerHTML = "×";
    removeBtn.onclick = function () {
      dropzone.removeFile(currentFile);
    };

    previewDiv.appendChild(img);
    previewDiv.appendChild(removeBtn);
    previewContainer.appendChild(previewDiv);
  }

  if (config.formId) {
    const form = document.getElementById(config.formId);
    if (form) {
      form.addEventListener("submit", function () {
        // ให้แน่ใจว่า input มีไฟล์ล่าสุดก่อน submit
        if (currentFile) {
          updateInput();
        }
      });
    }
  }

  return dropzone;
}

// Auto-initialize เมื่อ DOM พร้อม (ถ้าไม่มีการเรียกใช้เอง)
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function () {
    // ตรวจสอบว่ามี dropzone-area และยังไม่ได้ initialize
    const dropzoneArea = document.getElementById("dropzone-area");
    if (dropzoneArea && !dropzoneArea.dropzone) {
      // Auto-initialize with default config
      initDropzoneFormset();
    }
  });
} else {
  const dropzoneArea = document.getElementById("dropzone-area");
  if (dropzoneArea && !dropzoneArea.dropzone) {
    // Auto-initialize with default config
    initDropzoneFormset();
  }
}
