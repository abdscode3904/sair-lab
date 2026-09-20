document.addEventListener(
    "DOMContentLoaded",
    () => {

        const registerForm =
            document.getElementById(
                "registerForm"
            );

        const loginForm =
            document.getElementById(
                "loginForm"
            );


        if (registerForm) {
            registerForm.addEventListener(
                "submit",
                handleRegister
            );
        }


        if (loginForm) {
            loginForm.addEventListener(
                "submit",
                handleLogin
            );
        }

    }
);


async function handleRegister(event) {

    event.preventDefault();

    const form =
        event.currentTarget;

    const email =
        document
            .getElementById("email")
            .value
            .trim();

    const password =
        document
            .getElementById("password")
            .value;


    const button =
        form.querySelector(
            "button[type='submit']"
        );

    const message =
        document.getElementById(
            "formMessage"
        );


    if (!email || !password) {

        showMessage(
            message,
            "Please enter your email and password.",
            "error"
        );

        return;
    }


    setButtonLoading(
        button,
        true,
        "Creating account..."
    );


    try {

        const data =
            await apiRequest(
                "/api/auth/register",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        email,
                        password
                    })
                }
            );


        if (data.access_token) {

            saveToken(
                data.access_token
            );

            window.location.href =
                "dashboard.html";

            return;
        }


        showMessage(
            message,
            "Account created. Please log in.",
            "success"
        );


        setTimeout(
            () => {
                window.location.href =
                    "login.html";
            },
            900
        );


    } catch (error) {

        showMessage(
            message,
            error.message,
            "error"
        );

    } finally {

        setButtonLoading(
            button,
            false,
            "Create Account"
        );
    }
}


async function handleLogin(event) {

    event.preventDefault();

    const form =
        event.currentTarget;

    const email =
        document
            .getElementById("email")
            .value
            .trim();

    const password =
        document
            .getElementById("password")
            .value;


    const button =
        form.querySelector(
            "button[type='submit']"
        );

    const message =
        document.getElementById(
            "formMessage"
        );


    if (!email || !password) {

        showMessage(
            message,
            "Please enter your email and password.",
            "error"
        );

        return;
    }


    setButtonLoading(
        button,
        true,
        "Logging in..."
    );


    try {

        const data =
            await apiRequest(
                "/api/auth/login",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        email,
                        password
                    })
                }
            );


        if (!data.access_token) {
            throw new Error(
                "Login succeeded but no access token was returned."
            );
        }


        saveToken(
            data.access_token
        );


        window.location.href =
            "dashboard.html";


    } catch (error) {

        showMessage(
            message,
            error.message,
            "error"
        );

    } finally {

        setButtonLoading(
            button,
            false,
            "Login"
        );
    }
}


function showMessage(
    element,
    message,
    type
) {

    if (!element) {
        return;
    }

    element.textContent =
        message;

    element.className =
        `form-message ${type}`;
}


function setButtonLoading(
    button,
    loading,
    text
) {

    if (!button) {
        return;
    }

    button.disabled =
        loading;

    button.textContent =
        text;

    if (loading) {
        button.style.opacity =
            "0.65";
    } else {
        button.style.opacity =
            "1";
    }
}