
console.log("config.js loaded");

/* -----------------select_model.html----------------- */
function modelSelector() {
    return {
        models: [],
        currentModel: null,
        loading: true,
        selecting: false,
        error: '',
        successMessage: '',
        fastApiUrl: 'http://127.0.0.1:8001',
    
        formatDate(dateString) {
            if (!dateString) return 'N/A';
            try {
            const date = new Date(dateString);
            const thaiDate = date.toLocaleDateString('th-TH', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            return thaiDate;
            } catch (e) {
            return dateString;
            }
        },
    
        getModelPath(activeModelName) {
            if (!activeModelName || !this.models || this.models.length === 0) {
            return 'N/A';
            }
            
            // หา model ที่ตรงกับ active_model
            const activeModel = this.models.find(m => m.id === activeModelName || m.active);
            
            if (activeModel && activeModel.path) {
            // แสดงเฉพาะชื่อไฟล์ (ส่วนสุดท้ายของ path)
            const pathParts = activeModel.path.split('/');
            return pathParts[pathParts.length - 1] || activeModel.path;
            }
            
            return 'N/A';
        },
    
        async init() {
            await this.loadCurrentModel();
            await this.loadModels();
        },
    
        async loadCurrentModel() {
            try {
            const response = await fetch(`${this.fastApiUrl}/current-model`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            this.currentModel = data;
            } catch (error) {
            console.error('Error loading current model:', error);
            this.error = 'ไม่สามารถโหลดข้อมูล Model ปัจจุบันได้: ' + error.message;
            }
        },
    
        async loadModels() {
            this.loading = true;
            this.error = '';
            
            try {
            const response = await fetch(`${this.fastApiUrl}/models`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            this.models = data.models || [];
            
            // อัปเดต current model หลังจากโหลด models
            await this.loadCurrentModel();
            } catch (error) {
            console.error('Error loading models:', error);
            this.error = 'ไม่สามารถโหลดรายการ Model ได้: ' + error.message;
            this.models = [];
            } finally {
            this.loading = false;
            }
        },
    
        async selectModel(version) {
            if (this.selecting) return;
            
            this.selecting = true;
            this.error = '';
            this.successMessage = '';
    
            try {
            // ส่ง version เป็น query parameter
            const response = await fetch(`${this.fastApiUrl}/select-model?version=${encodeURIComponent(version)}`, {
                method: 'POST'
            });
    
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
    
            const data = await response.json();
            
            if (data.status === 'success') {
                this.successMessage = `เลือกใช้ Model "${data.active_model}" สำเร็จแล้ว`;
                
                // รีเฟรชข้อมูล models และ current model
                await this.loadModels();
                
                // ซ่อน success message หลังจาก 5 วินาที
                setTimeout(() => {
                this.successMessage = '';
                }, 5000);
            } else {
                throw new Error('การเลือก Model ไม่สำเร็จ');
            }
            } catch (error) {
            console.error('Error selecting model:', error);
            this.error = 'ไม่สามารถเลือก Model ได้: ' + error.message;
            } finally {
            this.selecting = false;
            }
        }
    }
}

/* -----------------SetautoTraining.html----------------- */

function countdownTimer(initialSeconds) {
    return {
        seconds: initialSeconds,
        timeLeft: '',
        
        init() {
            if (this.seconds > 0) {
            this.updateTimeLeft();
            setInterval(() => {
                if (this.seconds > 0) {
                this.seconds--;
                this.updateTimeLeft();
                }
            }, 1000);
            } else {
            this.timeLeft = "ถึงเวลาแล้ว/ปิดการทำงาน";
            }
        },
    
        updateTimeLeft() {
            const h = Math.floor(this.seconds / 3600);
            const m = Math.floor((this.seconds % 3600) / 60);
            const s = this.seconds % 60;
            this.timeLeft = `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        }
    }
}

function clockDisplay() {
    return {
        currentTime: '',
        currentDate: '',
    
        init() {
            this.updateClock();
            setInterval(() => this.updateClock(), 1000);
        },
    
        updateClock() {
            const now = new Date();
            
            // Format time: HH:MM:SS
            const time = now.toLocaleTimeString('th-TH', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
            });
            
            // Format date: Day, Date Month Year
            const date = now.toLocaleDateString('th-TH', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
            });
            
            this.currentTime = time;
            this.currentDate = date;
        }
    }
}

function trainingLog() {
    return {
        logs: [],
        isConnected: false,
        eventSource: null,
        fastApiUrl: 'http://127.0.0.1:8001/train-progress',
    
        connect() {
            if (this.isConnected) return;

            try {
            // สร้าง EventSource เพื่อเชื่อมต่อกับ SSE endpoint
            this.eventSource = new EventSource(this.fastApiUrl);
    
            // เมื่อได้รับข้อมูล
            this.eventSource.onmessage = (event) => {
                try {
                const data = JSON.parse(event.data);
                const timestamp = new Date().toLocaleTimeString('th-TH');
                const logMessage = `[${timestamp}] ${data.status || JSON.stringify(data)}`;
                this.logs.push(logMessage);
                
                // Auto scroll to bottom
                this.$nextTick(() => {
                    const container = this.$refs.logContainer;
                    if (container) {
                    container.scrollTop = container.scrollHeight;
                    }
                });
                } catch (e) {
                console.error('Error parsing SSE data:', e);
                const timestamp = new Date().toLocaleTimeString('th-TH');
                this.logs.push(`[${timestamp}] Error: ${event.data}`);
                }
            };
    
            // เมื่อเกิด error
            this.eventSource.onerror = (error) => {
                console.error('SSE Error:', error);
                const timestamp = new Date().toLocaleTimeString('th-TH');
                this.logs.push(`[${timestamp}] ❌ การเชื่อมต่อเกิดข้อผิดพลาด`);
                this.disconnect();
            };
    
            // เมื่อเชื่อมต่อสำเร็จ
            this.eventSource.onopen = () => {
                this.isConnected = true;
                const timestamp = new Date().toLocaleTimeString('th-TH');
                this.logs.push(`[${timestamp}] ✅ เชื่อมต่อสำเร็จ`);
            };
    
            } catch (error) {
            console.error('Failed to connect:', error);
            const timestamp = new Date().toLocaleTimeString('th-TH');
            this.logs.push(`[${timestamp}] ❌ ไม่สามารถเชื่อมต่อได้: ${error.message}`);
            }
        },
    
        disconnect() {
            if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
            }
            this.isConnected = false;
            const timestamp = new Date().toLocaleTimeString('th-TH');
            this.logs.push(`[${timestamp}] 🔌 ปิดการเชื่อมต่อแล้ว`);
        },
    
        clearLogs() {
            this.logs = [];
        }
    }
}
/* -----------------set_TestKNN.html----------------- */