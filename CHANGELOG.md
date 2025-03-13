# Changelog

## v2.12.0 (2025-03-13)

### Features


- Only look up _async_on_advertisement once per advertisement group (#108) ([`f7a001d`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f7a001d4288d0fec56a7467ebb6759c2658c40dd))


## v2.11.0 (2025-03-05)

### Features


- Reduce size of wheels (#105) ([`a52ad36`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a52ad36a8838a8516b7d533f0a5080c50ad9db7e))


## v2.10.2 (2025-03-04)

### Bug fixes


- Wheel builds (#104) ([`aa11ec3`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/aa11ec370e58572d79dda34e397013b0006d8ca7))


## v2.10.1 (2025-03-04)

### Bug fixes


- Add missing permissions to upload wheels (#103) ([`12b396f`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/12b396f8857b89b23ed978202eca37be33b7cf38))


## v2.10.0 (2025-03-04)

### Features


- Add optional cython for scanner to improve performance (#102) ([`a4e0803`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/a4e08034f3565fd086432402e68b20feb081a4df))


## v2.9.0 (2025-02-27)

### Features


- Use bluetooth_mac_address for the source if available (#100) ([`df7f72c`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/df7f72c18234ab95f2fcdc4322bab35d2065294c))


## v2.8.0 (2025-02-27)

### Features


- Simplify examples (#99) ([`c67c856`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c67c856207724f7ea81fd2f924a3f9940ddd58d8))


## v2.7.1 (2025-02-04)

### Bug fixes


- Update poetry to v2 (#93) ([`f1edae5`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/f1edae54bba1320c6f8292e837f14720baa79f13))


## v2.7.0 (2025-02-02)

### Features


- Avoid protobuf repeated container overhead (#90) ([`4a99c14`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4a99c14613c3243716e237d53816d821b12de2f4))


## v2.6.0 (2025-01-31)

### Features


- Update example to show how to use multiple devices (#85) ([`4a97019`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/4a97019bcf8baa7bfd4894d643d3f6c300de7603))


## v2.5.0 (2025-01-31)

### Features


- Reduce boilerplate in examples (#84) ([`03f3ff8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/03f3ff83d8f5719a53628d542a47e71988eb4599))


## v2.4.0 (2025-01-31)

### Features


- Simplify examples when using new habluetooth (#83) ([`1b38b3e`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1b38b3ef5f95b9df3fc3d71b123dadacd451852d))


## v2.3.0 (2025-01-31)

### Features


- Add example on connecting the scanner (#82) ([`b2d0eed`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/b2d0eedb5e22a448d41c2e65cfc4998a3e3972e2))


## v2.2.0 (2025-01-28)

### Features


- Add support for tracking bluetooth connection slot allocations (#74) ([`81fb130`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/81fb13001bf919962a26c51045c8acf4fd87f536))


## v2.1.1 (2025-01-22)

### Bug fixes


- Suppress duplicate connection changed callbacks (#73) ([`e3a5059`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/e3a505964ca3670e8f99450a4e33761026a5581b))


## v2.1.0 (2025-01-22)

### Features


- Update manager connection slot allocations on change (#70) ([`63045a7`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/63045a777088f28dded3c8e9f0a9959158af2348))


## v2.0.0 (2025-01-03)

### Bug fixes


- Move cache to device (#57) ([`2e44b28`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/2e44b284bc92967ccf1124dc9a78a9e04f0fb1f5))


### Refactoring


- Make wait_for_ble_connections_free require a timeout (#56) ([`72c0107`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/72c01078ed75686a8a6bd1ab0ed8243b0e69f99c))


## v1.1.1 (2024-12-22)

### Bug fixes


- Bump aioesphomeapi requirement to 27.0.0+ (#40) ([`1ab71d8`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/1ab71d812945c4d361272126b1c8bde68f171416))


### Unknown



## v1.1.0 (2024-10-05)

### Features


- Add support for python 3.13 (#19) ([`c3f2575`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c3f2575c9b942c1d89fb0f804b943678a6e75044))


## v1.0.0 (2024-02-18)

### Features


- Updates for aioesphomeapi 22 (#6) ([`c6a113a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c6a113a95313a22e47ccb6a1fda8c6e2e4b32850))


## v0.4.1 (2024-01-01)

### Performance improvements


- Avoid recreating enums from feature flags (#5) ([`00beb54`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/00beb54db075768069d9b48c1244866d2d402db2))


## v0.4.0 (2023-12-17)

### Features


- Add connect scanner helper (#4) ([`c4b110a`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/c4b110a6f3301af2d7a4bded236e2f5036a0d598))


## v0.3.0 (2023-12-14)

### Features


- Add available property to know when the esp device is connected (#3) ([`7732629`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/773262937fe106c573077a1f1d43156f00579f64))


## v0.2.0 (2023-12-13)

### Features


- Move mac_to_int helper to bluetooth_data_tools (#2) ([`79ff7da`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/79ff7da11cd360becf0e4c69c41c630d47b6fa13))


## v0.1.0 (2023-12-13)

### Features


- Initial import (#1) ([`7fa6be2`](https://github.com/Bluetooth-Devices/bleak-esphome/commit/7fa6be28a475781ebd90e7e0060bb0890b68b29b))


## v0.0.0 (2023-12-06)
