const API_URL = "https://n7omj6kh6k.execute-api.us-east-1.amazonaws.com/get-elevator-data";

let tempData = [];
let vibData = [];
let labels = [];

// 📊 Initialize Charts
const tempChart = new Chart(document.getElementById("tempChart"), {
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label: "Temperature",
            data: [],
            borderColor: "blue",
            fill: false,
            tension: 0.3
        }]
    },
    options: {
        responsive: true,
        animation: true,
        scales: {
            y: { beginAtZero: false }
        }
    }
});

const vibChart = new Chart(document.getElementById("vibChart"), {
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label: "Vibration",
            data: [],
            borderColor: "red",
            fill: false,
            tension: 0.3
        }]
    },
    options: {
        responsive: true,
        animation: true,
        scales: {
            y: { beginAtZero: false }
        }
    }
});

// 🔁 Fetch Data
async function fetchData() {
    try {
        const res = await fetch(API_URL + "?t=" + new Date().getTime());
        const data = await res.json();

        // 🔍 DEBUG
        console.log("API DATA:", data);

        // ✅ Safe latest record
        const latest = data.length > 0 ? data[0] : null;
        if (!latest) return;

        // 🟢 Update cards
        document.getElementById("elevator").innerText = latest.elevator_id;
        document.getElementById("door").innerText = latest.door_status;
        document.getElementById("people").innerText = latest.people_count;
        document.getElementById("temperature").innerText = latest.temperature + " °C";
        document.getElementById("weight").innerText = latest.weight;
        document.getElementById("vibration").innerText = latest.vibration;
        document.getElementById("status").innerText = latest.status;

        // 🎨 Status color
        const statusEl = document.getElementById("status");
        if (latest.status === "CRITICAL") {
            statusEl.style.color = "red";
        } else if (latest.status === "WARNING") {
            statusEl.style.color = "orange";
        } else {
            statusEl.style.color = "green";
        }

        // 🔥 Alert box
        const alertBox = document.getElementById("alertBox");

        if (latest.alerts.length > 0) {
            alertBox.innerText = "⚠ " + latest.alerts.join(", ");
            alertBox.style.background = "#ff4d4d";
            alertBox.style.animation = "blink 1s infinite";
        } else {
            alertBox.innerText = "✓ Elevator operating normally";
            alertBox.style.background = "#2ecc71";
            alertBox.style.animation = "none";
        }

        // 📈 Charts update
        const time = new Date().toLocaleTimeString();

        labels.push(time);
        tempData.push(latest.temperature);
        vibData.push(latest.vibration);

        // Limit data points
        if (labels.length > 10) {
            labels.shift();
            tempData.shift();
            vibData.shift();
        }

        tempChart.data.labels = labels;
        tempChart.data.datasets[0].data = tempData;
        tempChart.update();

        vibChart.data.labels = labels;
        vibChart.data.datasets[0].data = vibData;
        vibChart.update();

    } catch (error) {
        console.error("Fetch Error:", error);
    }
}

// 🔁 Auto refresh
setInterval(fetchData, 3000);

// 🚀 First load
fetchData();