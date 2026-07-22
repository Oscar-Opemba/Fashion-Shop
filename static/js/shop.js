/* Storefront behaviour layered on top of the theme's main.js.
   Everything here is progressive: each form still works without JS. */
(function () {
    'use strict';

    function csrfToken(form) {
        var input = form.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function updateHeader(data) {
        document.querySelectorAll('[data-cart-count]').forEach(function (el) {
            el.textContent = data.count;
        });
        document.querySelectorAll('[data-cart-total]').forEach(function (el) {
            el.textContent = 'KES ' + data.total;
        });

        var summary = document.querySelector('[data-cart-summary]');
        if (summary && data.summary_html) {
            summary.innerHTML = data.summary_html;
        }
    }

    function flash(message, isError) {
        var el = document.createElement('div');
        el.className = 'toast-note' + (isError ? ' toast-note--error' : '');
        el.textContent = message;
        document.body.appendChild(el);
        // Let the element land in the DOM before animating it in.
        requestAnimationFrame(function () { el.classList.add('is-visible'); });
        setTimeout(function () {
            el.classList.remove('is-visible');
            setTimeout(function () { el.remove(); }, 300);
        }, 2500);
    }

    // Add-to-cart without a page reload. On a phone a full reload loses the
    // shopper's place in the grid, which is the whole reason for doing this.
    document.addEventListener('submit', function (event) {
        var form = event.target.closest('[data-cart-form]');
        if (!form) return;

        event.preventDefault();

        var button = form.querySelector('button[type=submit]');
        if (button) button.disabled = true;

        fetch(form.action, {
            method: 'POST',
            body: new FormData(form),
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken(form)
            }
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return {ok: response.ok, data: data};
                });
            })
            .then(function (result) {
                if (!result.ok) {
                    flash(result.data.error || 'Could not update your cart.', true);
                    return;
                }
                updateHeader(result.data);
                flash('Added to your cart.');
            })
            .catch(function () {
                // Network trouble: fall back to a normal submit so the shopper
                // is never left wondering whether it worked.
                form.submit();
            })
            .finally(function () {
                if (button) button.disabled = false;
            });
    });

    // The product gallery now uses the theme's Bootstrap tabs, so no custom
    // image-swapping code is needed here.
})();
