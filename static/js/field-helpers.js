/**
 * Sri Basaveshwara Harvesting & Co. — Mobile Field Helpers
 * Version: 3.3.0
 * 
 * Includes:
 * 1. One-Tap WhatsApp Payment Receipts & Balance Reminders
 * 2. Web Speech API Voice-to-Text Dictation (Kannada, English, Hindi)
 * 3. Quick Field Remark Chips Inserter
 * 4. High-Contrast Outdoor Sunlight Mode & Night Mode Theme Controller
 */

(function (window, document) {
  'use strict';

  // =========================================================================
  // 1. WHATSAPP ENGINE & PHONE NORMALIZATION
  // =========================================================================

  /**
   * Normalizes an Indian phone number to 91XXXXXXXXXX format for wa.me.
   * @param {string|number} phone - Raw input phone number
   * @returns {string} Clean digits with 91 country prefix
   */
  function normalizePhone(phone) {
    if (!phone) return '';
    let cleaned = String(phone).replace(/[^\d]/g, '');
    if (cleaned.startsWith('0') && cleaned.length === 11) {
      cleaned = '91' + cleaned.substring(1);
    } else if (cleaned.length === 10) {
      cleaned = '91' + cleaned;
    }
    return cleaned;
  }

  /**
   * Opens WhatsApp with a pre-composed message for the given phone number.
   * @param {string} phone - Target phone number
   * @param {string} message - Message text
   */
  window.sendWhatsAppMessage = function (phone, message) {
    const cleanPhone = normalizePhone(phone);
    const encoded = encodeURIComponent(message || '');
    let url = '';
    if (cleanPhone && cleanPhone.length >= 10) {
      url = 'https://wa.me/' + cleanPhone + '?text=' + encoded;
    } else {
      url = 'https://wa.me/?text=' + encoded;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  /**
   * Generates and sends a polite, clear, and respectful Statement / Balance update to the farmer (no URLs, no emojis).
   * @param {Object} data - { name, phone, totalBilled, totalPaid, balanceDue }
   */
  window.sendWhatsAppReminder = function (data) {
    const name = data.name || 'Farmer';
    const balanceDue = Number(data.balanceDue || 0).toLocaleString('en-IN');
    const hasFullBreakdown = data.totalBilled && Number(data.totalBilled) > 0;

    let message =
      `*SRI BASAVESHWARA HARVESTING & CO.*\n\n` +
      `Namaste ${name} Ji,\n\n` +
      `Here is a summary of your harvesting account:\n\n`;

    if (hasFullBreakdown) {
      const totalBilled = Number(data.totalBilled || 0).toLocaleString('en-IN');
      const totalPaid = Number(data.totalPaid || 0).toLocaleString('en-IN');
      message +=
        `- Total Work Billed: *Rs. ${totalBilled}*\n` +
        `- Amount Received: *Rs. ${totalPaid}*\n` +
        `- *Pending Balance: Rs. ${balanceDue}*\n\n`;
    } else {
      message +=
        `- *Pending Balance: Rs. ${balanceDue}*\n\n`;
    }

    message +=
      `Kindly arrange the settlement at your convenience.\n\n` +
      `_If already paid, please ignore this message._\n\n` +
      `Thank you for your valuable support.`;

    window.sendWhatsAppMessage(data.phone, message);
  };

  /**
   * Generates and sends a single Machine Work / Harvesting Bill Receipt to the farmer (no emojis).
   * @param {Object} bill - { voucher, date, farmerName, phone, machine, acres, hours, gross, advance, balance, totalUdhar }
   */
  window.sendWhatsAppReceipt = function (bill) {
    const voucher = bill.voucher || 'Receipt';
    const date = bill.date || new Date().toLocaleDateString('en-IN');
    const farmerName = bill.farmerName || 'Farmer';
    const machine = bill.machine || 'Combine Harvester';
    const gross = Number(bill.gross || 0).toLocaleString('en-IN');
    const advance = Number(bill.advance || 0).toLocaleString('en-IN');
    const balanceAdded = Number(bill.balance || 0).toLocaleString('en-IN');
    const totalUdhar = Number(bill.totalUdhar || 0).toLocaleString('en-IN');

    let metrics = '';
    if (bill.acres && Number(bill.acres) > 0) {
      metrics += `${bill.acres} Acres`;
    }
    if (bill.hours && Number(bill.hours) > 0) {
      metrics += (metrics ? ` (${bill.hours} Hrs)` : `${bill.hours} Hours`);
    }
    if (!metrics) metrics = 'Harvesting Work';

    const message =
      `*SRI BASAVESHWARA HARVESTING & CO.*\n` +
      `*HARVESTING BILL RECEIPT*\n\n` +
      `Namaste ${farmerName} Ji,\n\n` +
      `- Bill No: *#${voucher}* (${date})\n` +
      `- Machine: ${machine}\n` +
      `- Work Done: ${metrics}\n` +
      `- Gross Bill: *Rs. ${gross}*\n` +
      `- Advance Paid: *Rs. ${advance}*\n` +
      `- *Added to Udhar: Rs. ${balanceAdded}*\n` +
      `- *Total Pending Udhar: Rs. ${totalUdhar}*\n\n` +
      `Thank you for choosing our harvesting services.`;

    window.sendWhatsAppMessage(bill.phone, message);
  };

  /**
   * Generates and sends a direct Payment Settlement Confirmation to the farmer (no emojis).
   * @param {Object} payment - { receiptNo, farmerName, phone, amount, method, date, remainingBalance }
   */
  window.sendWhatsAppPaymentSettlement = function (payment) {
    const receiptNo = payment.receiptNo || 'Receipt';
    const farmerName = payment.farmerName || 'Farmer';
    const amount = Number(payment.amount || 0).toLocaleString('en-IN');
    const method = payment.method || 'Cash';
    const date = payment.date || new Date().toLocaleDateString('en-IN');
    const remaining = Number(payment.remainingBalance || 0).toLocaleString('en-IN');

    const message =
      `*SRI BASAVESHWARA HARVESTING & CO.*\n` +
      `*PAYMENT COLLECTION RECEIPT*\n\n` +
      `Namaste ${farmerName} Ji,\n\n` +
      `We have received your payment with thanks:\n\n` +
      `- Received Amount: *Rs. ${amount}*\n` +
      `- Payment Mode: ${method}\n` +
      `- Receipt No: #${receiptNo} (${date})\n` +
      `- *Remaining Udhar: Rs. ${remaining}*\n\n` +
      `Thank you for settling your account.`;

    window.sendWhatsAppMessage(payment.phone, message);
  };


  // =========================================================================
  // 2. QUICK REMARKS CHIPS INSERTER
  // =========================================================================

  /**
   * Inserts or appends a quick pre-formatted remark chip into a target input or textarea.
   * @param {string} text - Chip label/text
   * @param {string} targetInputId - ID of textarea or input
   * @param {boolean} [replace=false] - If true, replaces existing text
   */
  window.insertQuickChip = function (text, targetInputId, replace) {
    const input = document.getElementById(targetInputId);
    if (!input) return;

    const currentVal = input.value.trim();
    if (!currentVal || replace) {
      input.value = text;
    } else {
      // Avoid duplicate tags
      const items = currentVal.split(/[,;\n]+/).map(s => s.trim().toLowerCase());
      if (!items.includes(text.toLowerCase())) {
        input.value = currentVal + (currentVal.endsWith(',') ? ' ' : ', ') + text;
      }
    }

    // Trigger standard input/change events for form bindings
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    input.focus();
  };


  // =========================================================================
  // 3. WEB SPEECH API VOICE-TO-TEXT HELPER
  // =========================================================================

  let activeRecognition = null;
  let activeMicButton = null;

  /**
   * Toggles speech recognition dictation for a specific input field.
   * @param {HTMLElement} btnEl - The mic button element
   * @param {string} targetInputId - ID of the target input/textarea
   * @param {string} [lang='kn-IN'] - Recognition language ('kn-IN', 'en-IN', 'hi-IN')
   */
  window.toggleVoiceDictation = function (btnEl, targetInputId, lang) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.');
      return;
    }

    const input = document.getElementById(targetInputId);
    if (!input) return;

    // If currently recording on this button, stop it
    if (activeRecognition) {
      activeRecognition.stop();
      activeRecognition = null;
      if (activeMicButton) {
        setMicButtonState(activeMicButton, false);
        activeMicButton = null;
      }
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = lang || 'kn-IN'; // Default to Kannada, falls back to Indian English/Hindi
      recognition.interimResults = true;
      recognition.continuous = false;
      recognition.maxAlternatives = 1;

      let initialText = input.value.trim();

      recognition.onstart = function () {
        activeRecognition = recognition;
        activeMicButton = btnEl;
        setMicButtonState(btnEl, true);
      };

      recognition.onresult = function (event) {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }

        if (transcript) {
          const separator = initialText ? ' ' : '';
          input.value = initialText + separator + transcript;
          input.dispatchEvent(new Event('input', { bubbles: true }));
        }
      };

      recognition.onerror = function (event) {
        console.warn('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
          alert('Microphone access was denied. Please allow microphone permissions in your browser settings.');
        }
        setMicButtonState(btnEl, false);
        activeRecognition = null;
        activeMicButton = null;
      };

      recognition.onend = function () {
        setMicButtonState(btnEl, false);
        activeRecognition = null;
        activeMicButton = null;
        input.dispatchEvent(new Event('change', { bubbles: true }));
      };

      recognition.start();
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      setMicButtonState(btnEl, false);
      activeRecognition = null;
      activeMicButton = null;
    }
  };

  function setMicButtonState(btnEl, isRecording) {
    if (!btnEl) return;
    if (isRecording) {
      btnEl.classList.add('recording-active');
      btnEl.setAttribute('aria-pressed', 'true');
      btnEl.title = 'Recording... Tap to Stop';
      const icon = btnEl.querySelector('i');
      if (icon) {
        icon.className = 'bi bi-mic-fill text-rose-500 animate-pulse';
      }
    } else {
      btnEl.classList.remove('recording-active');
      btnEl.setAttribute('aria-pressed', 'false');
      btnEl.title = 'Voice Dictation (Tap to Speak)';
      const icon = btnEl.querySelector('i');
      if (icon) {
        icon.className = 'bi bi-mic-fill';
      }
    }
  }


  // =========================================================================
  // 4. 3-WAY THEME CONTROLLER: DARK / LIGHT / SUNLIGHT (HIGH-CONTRAST)
  // =========================================================================

  /**
   * Applies the selected theme: 'dark' | 'light' | 'sunlight'
   * @param {string} mode
   */
  window.setTheme = function (mode) {
    const root = document.documentElement;
    root.classList.remove('dark', 'light', 'sunlight');
    root.removeAttribute('data-theme');

    if (mode === 'sunlight') {
      root.classList.add('sunlight');
      root.setAttribute('data-theme', 'sunlight');
      localStorage.setItem('agribos_theme', 'sunlight');
      localStorage.setItem('sbh_theme', 'sunlight');
    } else if (mode === 'light') {
      root.classList.add('light');
      root.setAttribute('data-theme', 'light');
      localStorage.setItem('agribos_theme', 'light');
      localStorage.setItem('sbh_theme', 'light');
    } else {
      root.classList.add('dark');
      root.setAttribute('data-theme', 'dark');
      localStorage.setItem('agribos_theme', 'dark');
      localStorage.setItem('sbh_theme', 'dark');
    }

    updateThemeIcons(mode);
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: { theme: mode } }));
  };

  /**
   * Cycles theme in order: Dark -> Light -> Sunlight -> Dark
   */
  window.cycleTheme = function () {
    const current = localStorage.getItem('sbh_theme') || localStorage.getItem('agribos_theme') || 'dark';
    let nextTheme = 'dark';
    if (current === 'dark') {
      nextTheme = 'light';
    } else if (current === 'light') {
      nextTheme = 'sunlight';
    } else {
      nextTheme = 'dark';
    }
    window.setTheme(nextTheme);
  };

  // Backward compatibility alias
  window.toggleTheme = window.cycleTheme;

  function updateThemeIcons(mode) {
    const sunIcons = document.querySelectorAll('.theme-icon-sun');
    const moonIcons = document.querySelectorAll('.theme-icon-moon');
    const sunlightIcons = document.querySelectorAll('.theme-icon-sunlight');
    const badge = document.getElementById('currentThemeLabel');

    if (badge) {
      if (mode === 'sunlight') badge.textContent = '☀️ Sunlight';
      else if (mode === 'light') badge.textContent = '🌤️ Light';
      else badge.textContent = '🌙 Dark';
    }
  }

  // =========================================================================
  // 5. CLIENT-SIDE IMAGE COMPRESSION (CAMERA & RECEIPT OPTIMIZATION)
  // =========================================================================

  /**
   * Compresses an image file client-side using HTML5 Canvas.
   * Resizes image to fit max dimension (1280px) and adjusts JPEG quality to meet <350KB target.
   * 
   * @param {File|Blob} file - Original image file
   * @param {Object} [options] - Configuration options
   * @param {number} [options.maxDimension=1280] - Maximum width/height in pixels
   * @param {number} [options.targetSizeKB=350] - Target file size in kilobytes
   * @param {number} [options.initialQuality=0.85] - Initial JPEG compression quality
   * @param {string} [options.outputType='image/jpeg'] - Output MIME type
   * @returns {Promise<File|Blob>} Resolves with compressed File/Blob or original file on failure
   */
  window.compressImage = function (file, options) {
    options = Object.assign({
      maxDimension: 1280,
      targetSizeKB: 350,
      initialQuality: 0.85,
      outputType: 'image/jpeg'
    }, options || {});

    return new Promise(function (resolve) {
      if (!file || !file.type || !file.type.startsWith('image/')) {
        // Not an image or invalid file, return untouched
        return resolve(file);
      }

      // Check canvas support
      if (!window.HTMLCanvasElement || !window.FileReader) {
        console.warn('Canvas/FileReader not supported. Bypassing client compression.');
        return resolve(file);
      }

      // If already small enough (under 350KB) and not oversized, return as-is
      if (file.size <= options.targetSizeKB * 1024 && file.type === 'image/jpeg') {
        return resolve(file);
      }

      const reader = new FileReader();
      reader.onerror = function () {
        console.warn('FileReader failed, returning original file.');
        resolve(file);
      };

      reader.onload = function (e) {
        const img = new Image();
        img.onerror = function () {
          console.warn('Image decoding failed, returning original file.');
          resolve(file);
        };

        img.onload = function () {
          try {
            let width = img.width;
            let height = img.height;

            // Calculate scaled dimensions preserving aspect ratio
            if (width > options.maxDimension || height > options.maxDimension) {
              if (width > height) {
                height = Math.round((height * options.maxDimension) / width);
                width = options.maxDimension;
              } else {
                width = Math.round((width * options.maxDimension) / height);
                height = options.maxDimension;
              }
            }

            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');

            if (!ctx) {
              return resolve(file);
            }

            // High-quality canvas rendering
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(img, 0, 0, width, height);

            // Progressive quality reduction loop
            const qualitySteps = [options.initialQuality, 0.70, 0.55, 0.40, 0.30];
            let currentStep = 0;

            function attemptExport() {
              const quality = qualitySteps[currentStep];
              canvas.toBlob(function (blob) {
                if (!blob) {
                  return resolve(file);
                }

                const targetSizeBytes = options.targetSizeKB * 1024;
                if (blob.size <= targetSizeBytes || currentStep >= qualitySteps.length - 1) {
                  // Construct a new File object with original name (ensuring .jpg extension)
                  let newName = file.name || 'receipt_capture.jpg';
                  if (!newName.toLowerCase().endsWith('.jpg') && !newName.toLowerCase().endsWith('.jpeg')) {
                    newName = newName.replace(/\.[^/.]+$/, '') + '.jpg';
                  }

                  try {
                    const compressedFile = new File([blob], newName, {
                      type: options.outputType,
                      lastModified: Date.now()
                    });
                    console.log(`Image compressed: ${(file.size / 1024).toFixed(1)}KB -> ${(compressedFile.size / 1024).toFixed(1)}KB (${width}x${height} @ Q:${quality})`);
                    resolve(compressedFile);
                  } catch (err) {
                    // Fallback for older browsers without File constructor
                    resolve(blob);
                  }
                } else {
                  currentStep++;
                  attemptExport();
                }
              }, options.outputType, quality);
            }

            attemptExport();
          } catch (err) {
            console.warn('Compression error:', err);
            resolve(file);
          }
        };

        img.src = e.target.result;
      };

      reader.readAsDataURL(file);
    });
  };

  /**
   * Attaches automatic client-side compression to a file input element.
   * Intercepts file selection, compresses images, and updates the DataTransfer files list.
   * 
   * @param {HTMLInputElement} inputEl
   * @param {Object} [options]
   */
  window.attachImageCompression = function (inputEl, options) {
    if (!inputEl || inputEl.dataset.compressionAttached === 'true') return;
    inputEl.dataset.compressionAttached = 'true';

    // Ensure camera capture hint is present if not already specified
    if (!inputEl.hasAttribute('accept')) {
      inputEl.setAttribute('accept', 'image/*');
    }

    inputEl.addEventListener('change', async function (e) {
      if (!inputEl.files || inputEl.files.length === 0) return;

      const files = Array.from(inputEl.files);
      let modified = false;

      // Show temporary processing state if indicator exists
      const statusEl = inputEl.closest('.upload-container')?.querySelector('.compression-status');
      if (statusEl) {
        statusEl.textContent = 'Compressing image...';
        statusEl.classList.remove('hidden');
      }

      try {
        const compressedFiles = await Promise.all(
          files.map(async (f) => {
            if (f.type && f.type.startsWith('image/')) {
              const compressed = await window.compressImage(f, options);
              if (compressed !== f) modified = true;
              return compressed;
            }
            return f;
          })
        );

        if (modified && window.DataTransfer) {
          const dt = new DataTransfer();
          compressedFiles.forEach(f => {
            if (f instanceof File) {
              dt.items.add(f);
            }
          });
          if (dt.files.length > 0) {
            inputEl.files = dt.files;
          }
        }

        if (statusEl) {
          statusEl.textContent = 'Optimized for mobile upload ✓';
          setTimeout(() => statusEl.classList.add('hidden'), 3000);
        }
      } catch (err) {
        console.warn('Auto compression failed, proceeding with original file.', err);
        if (statusEl) statusEl.classList.add('hidden');
      }
    });
  };

  // Auto-initialize on all receipt/fuel/image file inputs
  document.addEventListener('DOMContentLoaded', function () {
    const saved = localStorage.getItem('sbh_theme') || localStorage.getItem('agribos_theme') || 'dark';
    updateThemeIcons(saved);

    const imageInputs = document.querySelectorAll('input[type="file"][accept*="image"], input[type="file"].compress-image');
    imageInputs.forEach(input => window.attachImageCompression(input));
  });

})(window, document);
