# Changelog

## v3.3.0 (2025-09-08)

### Features


- Implement get_allocations for esphomescanner for thundering heard problem ([`ecd0454`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/ecd04542b7130fb963ca0f99cf04ba85e496783a))


## v3.2.0 (2025-08-28)

### Features


- Use set_*_mode helpers instead of setting mode directly ([`baa0b4c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/baa0b4c7edda076b9f0e496eafdd328fe2a426fe))


## v3.1.0 (2025-07-03)

### Features


- Add auto pair support for bleak 1.x ([`0d538e8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/0d538e8481b0e351b68bd977d431e2b29a38b381))


## v3.0.1 (2025-07-03)

### Bug fixes


- Use characteristic_properties ([`6bba94a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/6bba94aebc789fa7b40c46d41773bd74a054b9b0))


## v3.0.0 (2025-07-03)

### Features


- Add bleak 1.0 support ([`14dd2dd`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/14dd2dd068763680e3c34e3abe8870ecb3f71755))


## v2.16.0 (2025-06-03)

### Features


- Update scanner mode from callback ([`9c093b5`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/9c093b59885e0f3d7c68f8b1b5aa24ab76da4d49))


## v2.15.1 (2025-05-03)

### Bug fixes


- Revert to using python api for scanner ([`0cc7e99`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/0cc7e9962f380aa8064608a64c774f074a110fab))


## v2.15.0 (2025-04-29)

### Features


- Bump aioesphomeapi requirement to 30.1.0+ ([`4430f0c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4430f0c716804743247ba7a3b4efe593d6d2952f))


## v2.14.0 (2025-04-27)

### Features


- Switch to using the _async_on_raw_advertisement api ([`eb62775`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/eb6277517fb74955cffabfb162abf3a4815f02e3))


## v2.13.1 (2025-04-03)

### Bug fixes


- Disable 32bit wheels on linux to fix builds ([`4d922b8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4d922b82b073073e710a50da8b1b80be99166d2d))


## v2.13.0 (2025-04-03)

### Features


- Improve performance by cimporting base_scanner ([`a69de13`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a69de13dce134108cb018c4197aaeef1a07cfda2))


- Imporve performance by cimporting base_scanner ([`a69de13`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a69de13dce134108cb018c4197aaeef1a07cfda2))


- Imporve performance by cimporting base_scanner ([`a69de13`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a69de13dce134108cb018c4197aaeef1a07cfda2))


## v2.12.0 (2025-03-13)

### Features


- Only look up _async_on_advertisement once per advertisement group ([`f7a001d`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f7a001d4288d0fec56a7467ebb6759c2658c40dd))


## v2.11.0 (2025-03-05)

### Features


- Reduce size of wheels ([`a52ad36`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a52ad36a8838a8516b7d533f0a5080c50ad9db7e))


## v2.10.2 (2025-03-04)

### Bug fixes


- Wheel builds ([`aa11ec3`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/aa11ec370e58572d79dda34e397013b0006d8ca7))


## v2.10.1 (2025-03-04)

### Bug fixes


- Add missing permissions to upload wheels ([`12b396f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/12b396f8857b89b23ed978202eca37be33b7cf38))


- Add missing permissions to upload wheels ([`12b396f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/12b396f8857b89b23ed978202eca37be33b7cf38))


## v2.10.0 (2025-03-04)

### Features


- Add optional cython for scanner to improve performance ([`a4e0803`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a4e08034f3565fd086432402e68b20feb081a4df))


## v2.9.0 (2025-02-27)

### Features


- Use bluetooth_mac_address for the source if available ([`df7f72c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/df7f72c18234ab95f2fcdc4322bab35d2065294c))


## v2.8.0 (2025-02-27)

### Features


- Simplify examples ([`c67c856`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c67c856207724f7ea81fd2f924a3f9940ddd58d8))


## v2.7.1 (2025-02-04)

### Bug fixes


- Update poetry to v2 ([`f1edae5`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f1edae54bba1320c6f8292e837f14720baa79f13))


## v2.7.0 (2025-02-02)

### Features


- Avoid protobuf repeated container overhead ([`4a99c14`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4a99c14613c3243716e237d53816d821b12de2f4))


## v2.6.0 (2025-01-31)

### Features


- Update example to show how to use multiple devices ([`4a97019`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4a97019bcf8baa7bfd4894d643d3f6c300de7603))


## v2.5.0 (2025-01-31)

### Features


- Reduce boilerplate in examples ([`03f3ff8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/03f3ff83d8f5719a53628d542a47e71988eb4599))


## v2.4.0 (2025-01-31)

### Features


- Simplify examples when using new habluetooth ([`1b38b3e`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1b38b3ef5f95b9df3fc3d71b123dadacd451852d))


## v2.3.0 (2025-01-31)

### Features


- Add example on connecting the scanner ([`b2d0eed`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/b2d0eedb5e22a448d41c2e65cfc4998a3e3972e2))


## v2.2.0 (2025-01-28)

### Features


- Add support for tracking bluetooth connection slot allocations ([`81fb130`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/81fb13001bf919962a26c51045c8acf4fd87f536))


## v2.1.1 (2025-01-22)

### Bug fixes


- Suppress duplicate connection changed callbacks ([`e3a5059`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/e3a505964ca3670e8f99450a4e33761026a5581b))


## v2.1.0 (2025-01-22)

### Features


- Update manager connection slot allocations on change ([`63045a7`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/63045a777088f28dded3c8e9f0a9959158af2348))


## v2.0.0 (2025-01-03)

### Bug fixes


- Move cache to device ([`2e44b28`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/2e44b284bc92967ccf1124dc9a78a9e04f0fb1f5))


### Refactoring


- Make wait_for_ble_connections_free require a timeout ([`72c0107`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/72c01078ed75686a8a6bd1ab0ed8243b0e69f99c))


## v1.1.1 (2024-12-22)

### Bug fixes


- Bump aioesphomeapi requirement to 27.0.0+ ([`1ab71d8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1ab71d812945c4d361272126b1c8bde68f171416))


### Unknown



## v1.1.0 (2024-10-05)

### Features


- Add support for python 3.13 ([`c3f2575`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c3f2575c9b942c1d89fb0f804b943678a6e75044))


## v1.0.0 (2024-02-18)

### Features


- Updates for aioesphomeapi 22 ([`c6a113a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c6a113a95313a22e47ccb6a1fda8c6e2e4b32850))


## v0.4.1 (2024-01-01)

### Performance improvements


- Avoid recreating enums from feature flags ([`00beb54`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/00beb54db075768069d9b48c1244866d2d402db2))


## v0.4.0 (2023-12-17)

### Features


- Add connect scanner helper ([`c4b110a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c4b110a6f3301af2d7a4bded236e2f5036a0d598))


## v0.3.0 (2023-12-14)

### Features


- Add available property to know when the esp device is connected ([`7732629`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/773262937fe106c573077a1f1d43156f00579f64))


## v0.2.0 (2023-12-13)

### Features


- Move mac_to_int helper to bluetooth_data_tools ([`79ff7da`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/79ff7da11cd360becf0e4c69c41c630d47b6fa13))


## v0.1.0 (2023-12-13)

### Features


- Initial import ([`7fa6be2`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/7fa6be28a475781ebd90e7e0060bb0890b68b29b))


## v0.0.0 (2023-12-06)
