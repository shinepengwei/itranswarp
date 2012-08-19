/*
 * jQuery postJSON Plugin
 */

$.extend({
    postJSON: function(url, data, callback) {
        return jQuery.ajax({
            type: "POST",
            url: url,
            data: data,
            dataType: "json",
            success: callback
        });
    }
});
