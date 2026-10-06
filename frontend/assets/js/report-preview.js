// The sample stays readable without JavaScript. Topic controls reveal only after setup.
const controls = document.querySelector('.preview-controls');
if (controls) {
    const buttons = [...controls.querySelectorAll('button[aria-controls]')];
    controls.hidden = false;
    for (const button of buttons) {
        button.addEventListener('click', () => {
            for (const choice of buttons) {
                const selected = choice === button;
                choice.setAttribute('aria-pressed', String(selected));
                const page = document.getElementById(choice.getAttribute('aria-controls'));
                if (page) page.hidden = !selected;
            }
        });
    }
}
