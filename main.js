(function () {
  var ANALYTICS_CODE = '';
  if (ANALYTICS_CODE) {
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://gc.zgo.at/count.js';
    s.setAttribute('data-goatcounter', 'https://' + ANALYTICS_CODE + '.goatcounter.com/count');
    document.body.appendChild(s);
  }

  var btn = document.querySelector('.theme-btn');
  if (btn) {
    btn.addEventListener('click', function () {
      var root = document.documentElement;
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      try {
        localStorage.setItem('theme', next);
      } catch (e) {}
    });
  }

  var email = document.getElementById('copy-email');
  var copyStatus = document.getElementById('email-copy-status');
  if (email) {
    var original = email.textContent;
    var address = email.getAttribute('data-email') || original.trim();
    var resetTimer = null;
    email.addEventListener('click', function () {
      clearTimeout(resetTimer);
      email.disabled = true;
      if (copyStatus) copyStatus.textContent = '';
      var report = function (copied) {
        email.disabled = false;
        email.textContent = copied ? 'copied' : 'copy failed';
        if (copyStatus) {
          copyStatus.textContent = copied
            ? 'Email address copied.'
            : 'Could not copy. Select the email address or use the email link.';
        }
        resetTimer = setTimeout(function () {
          email.textContent = original;
        }, copied ? 1400 : 3000);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          navigator.clipboard.writeText(address).then(function () {
            report(true);
          }, function () {
            report(false);
          });
        } catch (e) {
          report(false);
        }
      } else {
        var previousFocus = document.activeElement;
        var ta = document.createElement('textarea');
        ta.value = address;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        var copied = false;
        try {
          ta.select();
          copied = document.execCommand('copy');
        } catch (e) {}
        document.body.removeChild(ta);
        if (previousFocus && previousFocus.focus) previousFocus.focus();
        report(copied);
      }
    });
  }
})();
