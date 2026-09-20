document.addEventListener("DOMContentLoaded", () => {

    const fileInput = document.getElementById("fileInput");
    const fileName = document.getElementById("fileName");
    const jobForm = document.getElementById("jobForm");
    const operation = document.getElementById("operation");
    const processButton = document.getElementById("processButton");
    const jobMessage = document.getElementById("jobMessage");

    const userEmail = document.getElementById("userEmail");
    const planBadge = document.getElementById("planBadge");
    const jobsUsed = document.getElementById("jobsUsed");
    const jobsRemaining = document.getElementById("jobsRemaining");

    const logoutButton = document.getElementById("logoutButton");

    const jobSection = document.getElementById("jobSection");
    const jobId = document.getElementById("jobId");
    const jobStatus = document.getElementById("jobStatus");
    const jobStatusText = document.getElementById("jobStatusText");
    const progressBar = document.getElementById("progressBar");
    const downloadButton = document.getElementById("downloadButton");

    let currentJobId = null;
    let pollingTimer = null;


    // -----------------------------------------------------
    // AUTH CHECK
    // -----------------------------------------------------

    if (!isLoggedIn()) {
        window.location.href = "login.html";
        return;
    }


    // -----------------------------------------------------
    // LOGOUT
    // -----------------------------------------------------

    logoutButton.addEventListener("click", () => {
        logout();
    });


    // -----------------------------------------------------
    // FILE SELECTION
    // -----------------------------------------------------

    fileInput.addEventListener("change", () => {

        if (!fileInput.files.length) {
            fileName.textContent = "Choose Excel or CSV file";
            return;
        }

        const file = fileInput.files[0];

        fileName.textContent = file.name;
    });


    // -----------------------------------------------------
    // LOAD ACCOUNT
    // -----------------------------------------------------

    async function loadAccount() {

        try {

            const data = await authenticatedRequest(
                "/api/auth/me"
            );

            const user = data.user || data;

            userEmail.textContent =
                user.email ||
                user.username ||
                "Account";

            planBadge.textContent =
                String(user.plan || "free").toUpperCase();

            await loadUsage();

        } catch (error) {

            removeToken();
            window.location.href = "login.html";
        }
    }


    // -----------------------------------------------------
    // LOAD USAGE
    // -----------------------------------------------------

    async function loadUsage() {

        try {

            const data = await authenticatedRequest(
                "/api/usage"
            );

            const usage = data.usage || data;

            jobsUsed.textContent =
                usage.jobs_count ??
                usage.jobs_used ??
                0;

            jobsRemaining.textContent =
                usage.remaining_jobs ??
                usage.jobs_remaining ??
                0;

        } catch (error) {

            console.error(
                "Usage loading failed:",
                error
            );
        }
    }


    // -----------------------------------------------------
    // SUBMIT JOB
    // -----------------------------------------------------

    jobForm.addEventListener("submit", async (event) => {

        event.preventDefault();

        jobMessage.textContent = "";
        jobMessage.className = "form-message";

        if (!fileInput.files.length) {

            showMessage(
                "Please select an Excel or CSV file.",
                "error"
            );

            return;
        }

        if (!operation.value) {

            showMessage(
                "Please select an operation.",
                "error"
            );

            return;
        }

        const file = fileInput.files[0];

        if (file.size > 25 * 1024 * 1024) {

            showMessage(
                "File is larger than the 25 MB limit.",
                "error"
            );

            return;
        }

        processButton.disabled = true;
        processButton.textContent = "Uploading...";

        const formData = new FormData();

        formData.append("file", file);
        formData.append("operation", operation.value);

        try {

            const token = getToken();

            const response = await fetch(
                `${API_BASE_URL}/api/jobs/upload`,
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`
                    },
                    body: formData
                }
            );

            let data = {};

            try {
                data = await response.json();
            } catch {
                data = {};
            }

            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    data.message ||
                    "Upload failed."
                );
            }

            currentJobId =
                data.job_id ||
                data.job?.job_id;

            if (!currentJobId) {

                throw new Error(
                    "Server did not return a job ID."
                );
            }

            showMessage(
                "File uploaded successfully.",
                "success"
            );

            showJob(data);

            await loadUsage();

            startPolling();

        } catch (error) {

            showMessage(
                error.message,
                "error"
            );

        } finally {

            processButton.disabled = false;
            processButton.textContent = "Process File";
        }
    });


    // -----------------------------------------------------
    // SHOW JOB
    // -----------------------------------------------------

    function showJob(data) {

        jobSection.classList.remove("hidden");

        jobId.textContent =
            currentJobId;

        const status =
            data.status ||
            data.job?.status ||
            "QUEUED";

        updateJobUI(status);
    }


    // -----------------------------------------------------
    // POLL JOB
    // -----------------------------------------------------

    function startPolling() {

        stopPolling();

        pollingTimer = setInterval(
            checkJobStatus,
            1500
        );

        checkJobStatus();
    }


    function stopPolling() {

        if (pollingTimer) {

            clearInterval(pollingTimer);
            pollingTimer = null;
        }
    }


    async function checkJobStatus() {

        if (!currentJobId) {
            return;
        }

        try {

            const data =
                await authenticatedRequest(
                    `/api/jobs/${currentJobId}`
                );

            const job =
                data.job ||
                data;

            const status =
                String(
                    job.status || "QUEUED"
                ).toUpperCase();

            updateJobUI(status);

            if (
                status === "COMPLETED" ||
                status === "FAILED"
            ) {

                stopPolling();

                if (status === "COMPLETED") {

                    prepareDownload();
                }
            }

        } catch (error) {

            console.error(
                "Job status error:",
                error
            );
        }
    }


    // -----------------------------------------------------
    // JOB UI
    // -----------------------------------------------------

    function updateJobUI(status) {

        jobStatus.textContent = status;

        if (status === "QUEUED") {

            progressBar.style.width = "20%";

            jobStatusText.textContent =
                "Your job is queued and waiting for processing.";

            downloadButton.classList.add("hidden");

        } else if (status === "PROCESSING") {

            progressBar.style.width = "50%";

            jobStatusText.textContent =
                "Sair Lab is processing your file...";

            downloadButton.classList.add("hidden");

        } else if (status === "QA") {

            progressBar.style.width = "80%";

            jobStatusText.textContent =
                "Quality checking the generated result...";

            downloadButton.classList.add("hidden");

        } else if (status === "COMPLETED") {

            progressBar.style.width = "100%";

            jobStatusText.textContent =
                "Processing completed successfully.";

        } else if (status === "FAILED") {

            progressBar.style.width = "100%";

            jobStatusText.textContent =
                "The job failed during processing.";

            downloadButton.classList.add("hidden");
        }
    }


    // -----------------------------------------------------
    // DOWNLOAD
    // -----------------------------------------------------

    function prepareDownload() {

        const token = getToken();

        downloadButton.href =
            `${API_BASE_URL}/api/jobs/${currentJobId}/download?token=${encodeURIComponent(token)}`;

        downloadButton.classList.remove("hidden");

        /*
         * The backend currently authenticates downloads
         * through the Authorization header.
         *
         * Therefore use a click handler instead of relying
         * only on the href.
         */

        downloadButton.onclick = async (event) => {

            event.preventDefault();

            try {

                const response = await fetch(
                    `${API_BASE_URL}/api/jobs/${currentJobId}/download`,
                    {
                        headers: {
                            "Authorization":
                                `Bearer ${token}`
                        }
                    }
                );

                if (!response.ok) {

                    let message =
                        "Download failed.";

                    try {

                        const data =
                            await response.json();

                        message =
                            data.detail ||
                            data.message ||
                            message;

                    } catch {}

                    throw new Error(message);
                }

                const blob =
                    await response.blob();

                const url =
                    URL.createObjectURL(blob);

                const a =
                    document.createElement("a");

                a.href = url;

                a.download =
                    getDownloadName();

                document.body.appendChild(a);

                a.click();

                a.remove();

                URL.revokeObjectURL(url);

            } catch (error) {

                showMessage(
                    error.message,
                    "error"
                );
            }
        };
    }


    function getDownloadName() {

        return `${currentJobId}_result`;
    }


    // -----------------------------------------------------
    // MESSAGE
    // -----------------------------------------------------

    function showMessage(message, type) {

        jobMessage.textContent = message;

        jobMessage.className =
            `form-message ${type}`;
    }


    // -----------------------------------------------------
    // START
    // -----------------------------------------------------

    loadAccount();

});