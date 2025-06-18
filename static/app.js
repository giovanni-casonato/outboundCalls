async function makeCall(event) {
    event.preventDefault();
    
    const phoneNumber = document.getElementById('phoneInput').value;
    const button = document.getElementById('callButton');
    const result = document.getElementById('result');
    
    // Disable button and show loading
    button.disabled = true;
    button.textContent = 'Calling...';
    result.style.display = 'none';
    
    try {
        const response = await fetch('/make-call', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `to_number=${encodeURIComponent(phoneNumber)}`
        });
        
        const data = await response.json();
        
        if (data.success) {
            result.className = 'result success';
            result.textContent = `Call initiated successfully to ${phoneNumber}`;
        } else {
            result.className = 'result error';
            result.textContent = `Error: ${data.error}`;
        }
        
    } catch (error) {
        result.className = 'result error';
        result.textContent = `Network error: ${error.message}`;
    }
    
    // Show result and reset button
    result.style.display = 'block';
    button.disabled = false;
    button.textContent = 'Call';
}