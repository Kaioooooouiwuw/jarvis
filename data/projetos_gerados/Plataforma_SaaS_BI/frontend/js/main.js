document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('a[href^="#"]').forEach(a => {
        a.addEventListener('click', e => { e.preventDefault(); document.querySelector(a.getAttribute('href')).scrollIntoView({ behavior: 'smooth' }); });
    });
    const obs = new IntersectionObserver(e => { e.forEach(en => { if (en.isIntersecting) { en.target.style.opacity='1'; en.target.style.transform='translateY(0)'; } }); }, { threshold: .1 });
    document.querySelectorAll('.section').forEach(el => { el.style.opacity='0'; el.style.transform='translateY(20px)'; el.style.transition='all .6s ease'; obs.observe(el); });
});