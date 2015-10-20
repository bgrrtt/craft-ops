<?php

// Environment to be used in craft/config/general.php
define('CRAFT_ENVIRONMENT', getenv('CRAFT_ENVIRONMENT'));

// Path to your craft/ folder
define('CRAFT_PATH', getenv('CRAFT_PATH'));

$bootstrap = rtrim(CRAFT_PATH, '/').'/app/bootstrap.php';

$craft = require_once $bootstrap;

$requiredPlugins = json_decode($_GET['plugins']);
$currentPlugins = $craft->plugins->getPlugins(false);

foreach ($currentPlugins as $name => $plugin) {
	if (in_array($name, $requiredPlugins)) {

		$pluginClassHandle = $plugin->getClassHandle();

		if (!$plugin->isInstalled) {
			echo "Installing $pluginClassHandle plugin.\n";
			$craft->plugins->installPlugin($pluginClassHandle);
		} elseif (!$plugin->isEnabled) {
			echo "Enabling $pluginClassHandle plugin.\n";
			$craft->plugins->enablePlugin($pluginClassHandle);
		} else {
			echo "Plugin $pluginClassHandle is already active.\n";
		}
	}
}
