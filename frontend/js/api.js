const API_BASE_URL = "https://sair-lab.onrender.com";
async function apiRequest(
    endpoint,
    options = {}
) {
    const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
            ...options,
            headers: {
                ...(options.headers || {})
            }
        }
    );

    let data = {};

    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        const message =
            data.detail ||
            data.message ||
            "Something went wrong.";

        throw new Error(message);
    }

    return data;
}


function saveToken(token) {
    localStorage.setItem(
        "sairlab_token",
        token
    );
}


function getToken() {
    return localStorage.getItem(
        "sairlab_token"
    );
}


function removeToken() {
    localStorage.removeItem(
        "sairlab_token"
    );
}


function isLoggedIn() {
    return Boolean(getToken());
}


async function authenticatedRequest(
    endpoint,
    options = {}
) {
    const token = getToken();

    if (!token) {
        throw new Error(
            "You are not logged in."
        );
    }

    const headers = {
        ...(options.headers || {}),
        "Authorization": `Bearer ${token}`
    };

    return apiRequest(
        endpoint,
        {
            ...options,
            headers
        }
    );
}


function logout() {
    removeToken();

    window.location.href =
        "login.html";
}