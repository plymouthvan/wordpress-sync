<?php
/**
 * Plugin Name: Change the color of the Admin Bar in Staging Environments
 * Description: Changes the admin bar background color to #e88a01 on staging sites.
 */

add_action('admin_bar_init', function() {
    if (is_admin_bar_showing() && is_staging_site()) {
        add_action('wp_head', 'custom_admin_bar_color');
        add_action('admin_head', 'custom_admin_bar_color');
    }
});

function is_staging_site() {
    $host = $_SERVER['HTTP_HOST'] ?? '';
    return strpos($host, 'staging.') === 0;
}

function custom_admin_bar_color() {
    echo '<style>
        #wpadminbar {
            background: #e88a01 !important;
        }
    </style>';
}