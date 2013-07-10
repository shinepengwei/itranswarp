// theme.js
function ajaxPostComment(form) {
    var $form = $(form);
    var $submit = $form.find('button[type=submit]');
    var $icon = $form.find('button[type=submit]>i');
    var $alert = $form.find('.alert');
    function _show_error(msg, field) {
        if (msg) {
            $alert.text(msg).show();
            $form.find('.field-' + field).addClass('error');
        }
        else {
            $alert.hide();
            $form.find('.field-' + field).removeClass('error');
        }
    };
    function _show_loading(is_loading) {
        if (is_loading) {
            $icon.addClass('loading');
            $submit.attr('disabled', 'disabled');
        }
        else {
            $icon.removeClass('loading');
            $submit.removeAttr('disabled');
        }
    };
    _show_error(null);
    _show_loading(true);
    $.postJSON($form.attr('action'), $form.serialize(), function(result) {
        location.reload();
    }, function(err) {
        _show_error(err.message || err.error, err.data);
        _show_loading(false);
    });
    return false;
}
